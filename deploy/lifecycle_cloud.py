"""Cloud/Kubernetes adapter. All mutations are invoked only by an explicitly executed lifecycle."""
import base64
import copy
import json
from pathlib import Path
import re
import shlex
import subprocess
import time
from urllib.parse import urlsplit

from deploy.commands import resolve
from deploy.configure import ROOT
from deploy.capacity import selected
from deploy.dataproc_submit import TERMINAL, release_key, spec, submit
from deploy.flink_control import application_id
from deploy.lifecycle_state import LifecycleError, context_key

class Cloud:
    def __init__(self, config, store, values, session=None, sleep=time.sleep, clock=time.monotonic):
        self.config, self.store, self.values = config, store, values
        if session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credential, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            session = AuthorizedSession(credential)
        self.session, self.sleep, self.clock = session, sleep, clock
        p, z, r, prefix = (config[k] for k in ("project_id", "zone", "region", "prefix"))
        self.project, self.zone, self.region, self.prefix = p, z, r, prefix
        self.cluster = f"https://container.googleapis.com/v1/projects/{p}/locations/{z}/clusters/{prefix}-gke"
        self.pool = self.cluster + "/nodePools/apps"
        self.dataproc = f"https://dataproc.googleapis.com/v1/projects/{p}/regions/{r}"
        self.sql = f"https://sqladmin.googleapis.com/v1/projects/{p}/instances/{prefix}-sql"
        self.kube = ["kubectl", "--kubeconfig", str(ROOT/".local-build/cloud/kubeconfig"),
                     "--context", f"gke_{p}_{z}_{prefix}-gke", "--request-timeout=20s"]
        self.pulse = lambda: None

    def request(self, method, url, body=None):
        response = self.session.request(method, url, json=body, timeout=30)
        if response.status_code not in {200, 201, 202}:
            raise LifecycleError("A cloud operation was rejected. Check authorized access and resource state; provider content was suppressed.")
        value = response.json()
        if not isinstance(value, dict):
            raise LifecycleError("Unexpected cloud response.")
        return value

    def command(self, args, payload=None, timeout=180):
        try:
            result = subprocess.run(resolve(args), cwd=ROOT, input=payload, capture_output=True,
                                    encoding="utf-8", check=True, timeout=timeout)
        except (subprocess.SubprocessError, OSError):
            raise LifecycleError("An authorized CLI operation failed. Provider output was suppressed; inspect access and resource readiness.")
        return result.stdout

    def kubectl(self, args, payload=None):
        raw = self.command(self.kube + args, payload)
        return json.loads(raw) if raw.strip() else {}

    def wait(self, check, label, timeout=900):
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            self.pulse()
            if check():
                return
            self.sleep(5)
        raise LifecycleError("Timed out waiting for " + label + ". Progress was retained; retry after inspection.")

    def operation(self, value, provider):
        name = value.get("name", "")
        if provider == "gke":
            if not re.fullmatch(r"operation-[A-Za-z0-9-]+", name):
                raise LifecycleError("Unexpected GKE operation identity.")
            url = f"https://container.googleapis.com/v1/projects/{self.project}/locations/{self.zone}/operations/{name}"
            complete = lambda v: v.get("status") == "DONE"
        elif provider == "dataproc":
            prefix = f"projects/{self.project}/regions/{self.region}/operations/"
            if not name.startswith(prefix) or not re.fullmatch(r"[A-Za-z0-9-]+", name[len(prefix):]):
                raise LifecycleError("Unexpected Dataproc operation identity.")
            url = "https://dataproc.googleapis.com/v1/" + name
            complete = lambda v: v.get("done") is True
        else:
            if not re.fullmatch(r"[A-Za-z0-9-]+", name):
                raise LifecycleError("Unexpected SQL operation identity.")
            url = f"https://sqladmin.googleapis.com/v1/projects/{self.project}/operations/{name}"
            complete = lambda v: v.get("status") == "DONE"
        def ready():
            result = self.request("GET", url)
            if result.get("error"):
                raise LifecycleError("Cloud operation ended with an error. Inspect the operation through the authorized console.")
            return complete(result)
        self.wait(ready, provider + " operation")

    def group(self, pool):
        urls = pool.get("instanceGroupUrls", [])
        if len(urls) != 1:
            raise LifecycleError("Lifecycle currently supports the configured single-zone node pool only.")
        path = urlsplit(urls[0])
        expected = f"/compute/v1/projects/{self.project}/zones/{self.zone}/instanceGroupManagers/"
        # GKE sometimes returns instanceGroups URLs; manager names are identical.
        alternate = expected.replace("instanceGroupManagers/", "instanceGroups/")
        if (path.scheme != "https" or path.netloc not in {"www.googleapis.com", "compute.googleapis.com"}
                or not path.path.startswith((expected, alternate))
                or path.query or path.fragment):
            raise LifecycleError("Node pool has an unexpected instance group destination.")
        name = path.path.rsplit("/", 1)[1]
        if not re.fullmatch(r"[a-z0-9-]+", name):
            raise LifecycleError("Invalid instance group identity.")
        return f"https://compute.googleapis.com/compute/v1/projects/{self.project}/zones/{self.zone}/instanceGroupManagers/{name}"

    def target_nodes(self, pool=None):
        pool = pool or self.request("GET", self.pool)
        return int(self.request("GET", self.group(pool))["targetSize"])

    def actual_nodes(self):
        manager = self.group(self.request("GET", self.pool))
        return int(self.request("GET", manager.replace("instanceGroupManagers/", "instanceGroups/"))["size"])

    def analytics_env(self):
        return {**self.values["env"], **self.values["managedFlink"]["env"]}

    def jobs(self):
        jobs = self.request("GET", self.dataproc + "/jobs?clusterName=" + self.prefix
            + "-flink&filter=labels.food_component%3Drestaurant-analytics&pageSize=100")
        if jobs.get("nextPageToken"):
            raise LifecycleError("Analytics history needs review before lifecycle execution.")
        return [row for row in jobs.get("jobs", [])
                if row.get("placement", {}).get("clusterName") == self.prefix + "-flink"]

    def job(self, identity):
        if not re.fullmatch(r"food-analytics-[0-9a-f]{20}", identity):
            raise LifecycleError("Unexpected analytics job identity.")
        return self.request("GET", self.dataproc + "/jobs/" + identity)

    def overview(self):
        gke = self.request("GET", self.cluster)
        pool = self.request("GET", self.pool)
        dataproc = self.request("GET", self.dataproc + "/clusters/" + self.prefix + "-flink")
        sql = self.request("GET", self.sql)
        return {"gke": gke, "pool": pool, "nodes": self.target_nodes(pool), "dataproc": dataproc, "sql": sql}

    def snapshot(self):
        actual = self.overview()
        _, capacity = selected(self.config)
        if (actual["gke"].get("status") != "RUNNING"
                or actual["gke"].get("autoscaling", {}).get("enableNodeAutoprovisioning")
                or actual["nodes"] != capacity["gke_nodes"]
                or actual["pool"].get("config", {}).get("machineType") != capacity["gke_machine"]
                or actual["sql"].get("settings", {}).get("tier") != capacity["sql_tier"]
                or actual["sql"].get("settings", {}).get("activationPolicy", "ALWAYS") != "ALWAYS"
                or actual["dataproc"].get("status", {}).get("state") != "RUNNING"):
            raise LifecycleError("Deployment is not in the expected running profile. Review capacity and state before pausing.")
        autoscaling = actual["pool"].get("autoscaling", {})
        if (autoscaling.get("totalMaxNodeCount", autoscaling.get("maxNodeCount", capacity["gke_nodes"]))
                > capacity["gke_max_nodes"]):
            raise LifecycleError("Live autoscaling exceeds the selected profile cap.")
        policy, _ = self.store.read("kafka_policy")
        if (not policy or policy.get("schema_version") != 1 or policy.get("context_key") != context_key(self.config)
                or policy.get("cluster_id") != self.config["kafka_cluster_id"]
                or policy.get("broker") != self.values["env"]["KAFKA_BOOTSTRAP_SERVERS"]
                or policy.get("retention_days") != int(self.values["env"].get("KAFKA_RETENTION_DAYS", "21"))):
            raise LifecycleError("Apply the reviewed Kafka retention policy before pausing; its private receipt is missing or mismatched.")
        kube_config = self.kubectl(["config", "view", "--minify", "-o", "json"])
        servers = [v["cluster"]["server"] for v in kube_config.get("clusters", [])]
        if servers != ["https://" + actual["gke"]["endpoint"]]:
            raise LifecycleError("Kubeconfig points at a different cluster endpoint.")
        objects = self.kubectl(["get", "deployments", "-n", "food", "-l", "part-of=food", "-o", "json"])
        deployments = {}
        for obj in objects.get("items", []):
            name = obj["metadata"]["name"]
            if name not in self.values["workloads"]:
                raise LifecycleError("Unexpected application workload; refusing a partial pause.")
            containers = obj["spec"]["template"]["spec"]["containers"]
            app = next(v for v in containers if v["name"] == "application")
            if app["image"] != self.values["image"]:
                raise LifecycleError("Deployed image differs from reviewed configuration.")
            count = obj["spec"].get("replicas", 1)
            if count < 1:
                raise LifecycleError("A workload is already scaled down without a lifecycle snapshot.")
            deployments[name] = count
        if set(deployments) != set(self.values["workloads"]):
            raise LifecycleError("Not all expected application workloads are deployed.")
        hpas = self.kubectl(["get", "hpa", "-n", "food", "-o", "json"])
        expected_hpas = {name for name, item in self.values["workloads"].items() if item.get("hpa")}
        if {v["metadata"]["name"] for v in hpas.get("items", [])} != expected_hpas:
            raise LifecycleError("Both expected application HPAs must exist before pausing.")
        for obj in hpas.get("items", []):
            if obj["spec"].get("minReplicas", 1) < 1:
                raise LifecycleError("HPA scale-to-zero metrics need an explicit maintenance integration.")
        zk = self.kubectl(["get", "statefulset", "zookeeper", "-n", "food", "-o", "json"])
        if zk["spec"].get("replicas") != 3 or zk.get("status", {}).get("readyReplicas") != 3:
            raise LifecycleError("ZooKeeper must have its three persistent members ready before pausing.")
        active_jobs = self.kubectl(["get", "jobs", "-n", "food", "-o", "json"])
        if any(v.get("status", {}).get("active", 0) for v in active_jobs.get("items", [])):
            raise LifecycleError("Finish bootstrap, analytics hooks and load-test jobs before pausing.")
        argo = {}
        for name in ("food-root", "food-platform", "food"):
            obj = self.kubectl(["get", "application", name, "-n", "argocd", "-o", "json"])
            if obj.get("status", {}).get("operationState", {}).get("phase") in {"Running", "Terminating"}:
                raise LifecycleError("Wait for active GitOps operations before pausing.")
            if obj["spec"]["source"]["targetRevision"] != self.config["git_revision"]:
                raise LifecycleError("GitOps revision differs from reviewed local configuration.")
            argo[name] = copy.deepcopy(obj["spec"].get("syncPolicy", {}))
        running = [v for v in self.jobs() if v.get("status", {}).get("state") not in TERMINAL]
        if len(running) != 1 or running[0].get("status", {}).get("state") != "RUNNING":
            raise LifecycleError("Expected exactly one healthy analytics run.")
        job = running[0]
        expected = spec(self.analytics_env())[2]
        if (job.get("labels", {}).get("food_protocol") != "1"
                or job.get("labels", {}).get("food_release") != release_key(self.analytics_env())[:20]
                or any(job.get("flinkJob", {}).get(k) != expected["flinkJob"][k]
                       for k in ("mainClass", "jarFileUris", "args"))):
            raise LifecycleError("Analytics does not match the lifecycle-aware release.")
        identity = job["reference"]["jobId"]
        self.job(identity)
        try:
            yarn_identity = application_id(job)
        except ValueError:
            yarn_identity = None  # The remote probe resolves the unique explicit YARN application name.
        if job.get("flinkJob", {}).get("properties", {}).get("yarn.application.name") != identity:
            raise LifecycleError("Analytics must use its explicit lifecycle YARN application name.")
        return {"kafka_retention_days": policy["retention_days"], "profile": self.config.get("compute_profile", "demo"),
            "image": self.values["image"], "release_key": release_key(self.analytics_env()),
            "gke_created": actual["gke"]["createTime"], "dataproc_uuid": actual["dataproc"]["clusterUuid"],
            "sql_created": actual["sql"]["createTime"], "nodes": actual["nodes"],
            "autoscaling": autoscaling, "pool_groups": actual["pool"]["instanceGroupUrls"], "deployments": deployments, "argo": argo,
            "job_id": identity, "application_id": yarn_identity}

    def validate_snapshot(self, snapshot):
        if (snapshot["profile"] != self.config.get("compute_profile", "demo")
                or snapshot["image"] != self.values["image"]
                or snapshot["release_key"] != release_key(self.analytics_env())):
            raise LifecycleError("Configuration changed while paused. Restore the recorded release before resuming.")
        actual = self.overview()
        if (actual["gke"].get("createTime") != snapshot["gke_created"]
                or actual["dataproc"].get("clusterUuid") != snapshot["dataproc_uuid"]
                or actual["pool"].get("instanceGroupUrls") != snapshot["pool_groups"]
                or actual["sql"].get("createTime") != snapshot["sql_created"]):
            raise LifecycleError("A resource was recreated; do not apply a stale pause snapshot.")

    def argo_sync(self, name, policy):
        self.kubectl(["patch", "application", name, "-n", "argocd", "--type=merge",
                      "-p", json.dumps({"spec": {"syncPolicy": policy}}), "-o", "json"])

    def suspend_gitops(self, snapshot):
        for name in ("food-root", "food-platform", "food"):
            policy = copy.deepcopy(snapshot["argo"][name])
            policy["automated"] = None
            self.argo_sync(name, policy)
            def settled():
                obj = self.kubectl(["get", "application", name, "-n", "argocd", "-o", "json"])
                return not obj["spec"].get("syncPolicy", {}).get("automated") and obj.get("status", {}).get("operationState", {}).get("phase") not in {"Running", "Terminating"}
            self.wait(settled, "GitOps maintenance suspension", 300)

    def restore_gitops(self, snapshot):
        for name in ("food-platform", "food", "food-root"):
            # Clear the operational override before restoring the exact previous policy.
            self.argo_sync(name, None)
            self.argo_sync(name, snapshot["argo"][name])

    def autoscaling(self, setting):
        current = self.request("GET", self.pool).get("autoscaling", {})
        keys = ("enabled", "minNodeCount", "maxNodeCount", "totalMinNodeCount", "totalMaxNodeCount", "locationPolicy")
        wanted = {k: setting[k] for k in keys if k in setting}
        if any(current.get(k) != v for k, v in wanted.items()):
            self.operation(self.request("POST", self.pool + ":setAutoscaling", {"autoscaling": wanted}), "gke")

    def resize(self, count):
        if self.target_nodes() != count:
            self.operation(self.request("POST", self.pool + ":setSize", {"nodeCount": count}), "gke")
        self.wait(lambda: self.target_nodes() == count and self.actual_nodes() == count, "node pool size")

    def scale_workloads(self, counts):
        ordered = sorted(counts, key=lambda name: (name != "web-ui", name))
        for name in ordered:
            self.kubectl(["scale", "deployment", name, "-n", "food", "--replicas=" + str(counts[name]), "-o", "json"])
        if not any(counts.values()):
            def stopped():
                pods = self.kubectl(["get", "pods", "-n", "food", "-l", "part-of=food", "-o", "json"])
                return not any(v["metadata"].get("labels", {}).get("app") in counts
                               for v in pods.get("items", []))
            self.wait(stopped, "application pods to terminate", 300)

    def set_zookeeper(self, count):
        self.kubectl(["scale", "statefulset", "zookeeper", "-n", "food", "--replicas=" + str(count), "-o", "json"])
        if count == 0:
            self.wait(lambda: not self.kubectl(["get", "pods", "-n", "food", "-l", "app=zookeeper", "-o", "json"]).get("items"), "ZooKeeper shutdown", 300)
        else:
            def quorum_ready():
                obj = self.kubectl(["get", "statefulset", "zookeeper", "-n", "food", "-o", "json"])
                return obj.get("status", {}).get("readyReplicas") == 3 and obj.get("status", {}).get("observedGeneration", 0) >= obj["metadata"]["generation"]
            self.wait(quorum_ready, "ZooKeeper quorum", 600)

    def sql_idle(self):
        url = f"https://sqladmin.googleapis.com/v1/projects/{self.project}/operations?instance={self.prefix}-sql&maxResults=100"
        return all(row.get("status") == "DONE" for row in self.request("GET", url).get("items", []))

    def set_sql(self, policy):
        current = self.request("GET", self.sql)
        if current["settings"].get("activationPolicy", "ALWAYS") != policy:
            self.operation(self.request("PATCH", self.sql, {"settings": {"activationPolicy": policy}}), "sql")
        # A prior PATCH response may have been lost after acceptance. Its setting can
        # be visible before the VM transition finishes; reconcile pending operations.
        self.wait(self.sql_idle, "Cloud SQL activation transition")

    def set_dataproc(self, state):
        name = self.dataproc + "/clusters/" + self.prefix + "-flink"
        actual = self.request("GET", name)["status"]["state"]
        desired = "RUNNING" if state == "start" else "STOPPED"
        if actual != desired:
            if actual in {"STARTING", "STOPPING", "UPDATING", "CREATING"}:
                self.wait(lambda: self.request("GET", name)["status"]["state"] not in
                          {"STARTING", "STOPPING", "UPDATING", "CREATING"}, "prior analytics operation")
            if self.request("GET", name)["status"]["state"] != desired:
                self.operation(self.request("POST", name + ":" + state, {}), "dataproc")
        self.wait(lambda: self.request("GET", name)["status"]["state"] == desired, "analytics cluster " + desired)

    def stop_analytics(self, snapshot, target):
        # Retry after a lost SSH response: find its durable completed metadata first.
        recovered = self.store.recover_savepoint(target)
        job = self.job(snapshot["job_id"])
        if recovered:
            self.wait(lambda: self.job(snapshot["job_id"])["status"]["state"] in TERMINAL, "analytics termination")
            return recovered
        if job["status"]["state"] != "RUNNING":
            raise LifecycleError("Analytics ended without a confirmed savepoint; retain resources for recovery.")
        from deploy import flink_control
        script = base64.b64encode(Path(flink_control.__file__).read_bytes()).decode()
        payload = base64.b64encode(json.dumps({"application_id": snapshot["application_id"], "job_name": snapshot["job_id"], "target": target}).encode()).decode()
        remote = "python3 -c " + shlex.quote("import base64;exec(base64.b64decode(" + repr(script) + "))") + " " + shlex.quote(payload)
        self.pulse()
        raw = self.command(["gcloud", "compute", "ssh", self.prefix + "-flink-m", "--project", self.project,
            "--zone", self.zone, "--tunnel-through-iap", "--quiet", "--command", remote], timeout=750)
        # Only the final bounded helper result is interpreted; SSH output is never printed.
        try:
            value = json.loads(raw.strip().splitlines()[-1])
            uri = value["savepoint_uri"]
        except (ValueError, KeyError, IndexError):
            raise LifecycleError("Savepoint response was lost. Retry pause to inspect durable metadata.")
        if not uri.startswith(target.rstrip("/") + "/savepoint-") or not self.store.savepoint_exists(uri):
            raise LifecycleError("Durable savepoint metadata was not confirmed.")
        self.wait(lambda: self.job(snapshot["job_id"])["status"]["state"] in TERMINAL, "analytics termination")
        return uri

    def start_analytics(self, run_id, savepoint):
        env = {**self.analytics_env(), "ANALYTICS_RUN_ID": run_id, "ANALYTICS_SAVEPOINT": savepoint}
        identity, _ = submit(self.session, env)
        def ready():
            state = self.job(identity)["status"]["state"]
            if state in TERMINAL:
                raise LifecycleError("Restored analytics run failed. Retain its state and inspect Dataproc.")
            return state == "RUNNING"
        self.wait(ready, "restored analytics run")
        return identity

    def readiness(self):
        def ready():
            deployments = self.kubectl(["get", "deployments", "-n", "food", "-l", "part-of=food", "-o", "json"])
            rows = {v["metadata"]["name"]: v for v in deployments.get("items", [])}
            if set(rows) != set(self.values["workloads"]):
                return False
            if any(v.get("status", {}).get("observedGeneration", 0) < v["metadata"]["generation"]
                   or v.get("status", {}).get("availableReplicas", 0) < v["spec"].get("replicas", 1)
                   or v["spec"].get("replicas", 1) < 1 for v in rows.values()):
                return False
            zk = self.kubectl(["get", "statefulset", "zookeeper", "-n", "food", "-o", "json"])
            return zk.get("status", {}).get("readyReplicas") == 3 and zk.get("status", {}).get("observedGeneration", 0) >= zk["metadata"]["generation"]
        self.wait(ready, "application readiness and ZooKeeper quorum", 900)

    def assert_paused(self):
        actual = self.overview()
        if (actual["nodes"] != 0 or self.actual_nodes() != 0 or not self.sql_idle() or actual["pool"].get("autoscaling", {}).get("enabled")
                or actual["sql"]["settings"].get("activationPolicy") != "NEVER"
                or actual["dataproc"]["status"]["state"] != "STOPPED"):
            raise LifecycleError("Pause did not reach all expected stopped states.")

    def gitops_readiness(self):
        def ready():
            for name in ("food-root", "food-platform", "food"):
                obj = self.kubectl(["get", "application", name, "-n", "argocd", "-o", "json"])
                status = obj.get("status", {})
                if status.get("sync", {}).get("status") != "Synced" or status.get("health", {}).get("status") != "Healthy":
                    return False
                if status.get("operationState", {}).get("phase") in {"Running", "Terminating"}:
                    return False
            return True
        self.wait(ready, "GitOps applications to become Healthy and Synced", 900)
