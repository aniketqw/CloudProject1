"""Private GCS lifecycle journal and generation-fenced operator lease; no secret values."""
import copy
import hashlib
import json
import re
import time
import uuid
from urllib.parse import urlsplit

class LifecycleError(RuntimeError):
    pass

def gs_parts(uri):
    parsed = urlsplit(uri)
    if (parsed.scheme != "gs" or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", parsed.netloc)
            or parsed.query or parsed.fragment or not parsed.path.strip("/")
            or any(v in {".", "..", ""} for v in parsed.path.strip("/").split("/"))):
        raise LifecycleError("Invalid protected Cloud Storage URI.")
    return parsed.netloc, parsed.path.lstrip("/")

def locations(config):
    bucket = config["project_id"] + "-" + config["prefix"] + "-checkpoints"
    return {
        "journal": "gs://" + bucket + "/lifecycle/journal.json",
        "control": "gs://" + bucket + "/lifecycle/analytics.json",
        "kafka_policy": "gs://" + bucket + "/lifecycle/kafka-policy.json",
        "savepoints": "gs://" + bucket + "/flink/savepoints/",
    }

def destination(config):
    return {k: config[k] for k in ("project_id", "region", "zone", "prefix")}

def context_key(config):
    return hashlib.sha256(json.dumps(destination(config), sort_keys=True).encode()).hexdigest()

class GCSStore:
    def __init__(self, config, client=None):
        if client is None:
            from google.cloud import storage
            client = storage.Client(project=config["project_id"])
        self.client = client
        self.paths = locations(config)

    def read(self, kind):
        from google.api_core.exceptions import NotFound, PreconditionFailed
        bucket, path = gs_parts(self.paths[kind])
        blob = self.client.bucket(bucket).blob(path)
        try:
            blob.reload()
            generation = int(blob.generation)
            value = json.loads(blob.download_as_bytes(if_generation_match=generation))
        except NotFound:
            return None, 0
        except PreconditionFailed:
            raise LifecycleError("Lifecycle state changed concurrently. Retry the read.")
        if not isinstance(value, dict):
            raise LifecycleError("Lifecycle record is malformed; operator review is required.")
        return value, generation

    def write(self, kind, value, generation):
        from google.api_core.exceptions import PreconditionFailed
        bucket, path = gs_parts(self.paths[kind])
        blob = self.client.bucket(bucket).blob(path)
        try:
            blob.upload_from_string(json.dumps(value, sort_keys=True), content_type="application/json",
                                    if_generation_match=generation)
        except PreconditionFailed:
            raise LifecycleError("Another operator changed lifecycle state. No further action was taken.")
        return int(blob.generation)

    def savepoint_exists(self, uri):
        bucket, path = gs_parts(uri.rstrip("/") + "/_metadata")
        blob = self.client.bucket(bucket).get_blob(path)
        return bool(blob and blob.size and int(blob.size) > 0)

    def recover_savepoint(self, prefix):
        bucket, path = gs_parts(prefix.rstrip("/") + "/")
        found = []
        for index, blob in enumerate(self.client.list_blobs(bucket, prefix=path.rstrip("/") + "/")):
            if index > 4096:
                raise LifecycleError("Savepoint inventory exceeded the bounded recovery scan.")
            suffix = blob.name[len(path.rstrip("/") + "/"):]
            if re.fullmatch(r"savepoint-[A-Za-z0-9-]+/_metadata", suffix) and blob.size:
                found.append("gs://" + bucket + "/" + blob.name.rsplit("/", 1)[0])
        if len(found) > 1:
            raise LifecycleError("Multiple savepoints found for one pause. Review rather than guessing.")
        return found[0] if found else None

class Journal:
    def __init__(self, store, config, clock=time.time):
        self.store, self.config, self.clock = store, config, clock
        self.value, self.generation = store.read("journal")
        self.owner = None
        if self.value:
            if self.value.get("schema_version") != 1 or self.value.get("destination") != destination(config):
                raise LifecycleError("Lifecycle journal belongs to a different deployment or protocol.")

    def acquire(self, action, recover=False):
        now = self.clock()
        value = copy.deepcopy(self.value) if self.value else {
            "schema_version": 1, "destination": destination(self.config), "phase": "running",
            "completed": [], "history": []}
        lock = value.get("lock")
        if lock and (lock.get("expires_at", 0) > now or not recover):
            raise LifecycleError("Another lifecycle operation holds the lease. Use --recover only after an expired operation is confirmed stopped.")
        self.owner = uuid.uuid4().hex
        value["lock"] = {"owner": self.owner, "action": action, "expires_at": now + 1800}
        self.value = value
        self.persist()

    def persist(self):
        if self.owner:
            self.value["lock"] = {"owner": self.owner, "action": self.value["lock"]["action"],
                                  "expires_at": self.clock() + 1800}
        self.value["updated_at"] = self.clock()
        self.generation = self.store.write("journal", self.value, self.generation)

    def heartbeat(self):
        self.persist()

    def release(self, error=None):
        if not self.owner:
            return
        self.value["lock"] = None
        if error:
            self.value["last_error"] = "Operation interrupted; completed steps were retained. Re-run or inspect status."
        else:
            self.value.pop("last_error", None)
        self.owner = None
        self.persist()

def read_control(store, config, release_key):
    value, generation = store.read("control")
    if value:
        if value.get("schema_version") != 1 or value.get("context_key") != context_key(config):
            raise LifecycleError("Analytics control record belongs to a different deployment.")
        if value.get("release_key") != release_key:
            raise LifecycleError("Analytics release changed. Use the documented savepoint migration procedure.")
    return value, generation

def guard_running(config, store=None):
    """Used before Terraform mutation: the lifecycle journal must not be paused or busy."""
    journal = Journal(store or GCSStore(config), config).value
    if journal and (journal.get("phase") != "running" or journal.get("lock")):
        raise LifecycleError("Deployment is paused or a lifecycle operation is unfinished. Resume it before applying Terraform.")
