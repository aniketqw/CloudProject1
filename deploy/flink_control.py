"""Bounded, credential-free Flink stop-with-savepoint probe executed on its private master."""
import base64
import json
import re
import sys
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

def application_id(job):
    found = set()
    for application in job.get("yarnApplications", []):
        if application.get("state") not in {"RUNNING", "ACCEPTED"}:
            continue
        for value in (application.get("name", ""), application.get("trackingUrl", "")):
            found.update(re.findall(r"application_[0-9]+_[0-9]+", value))
    if len(found) != 1:
        raise ValueError("Expected exactly one active YARN application.")
    return found.pop()

def stop(payload, request=None, clock=time.monotonic, sleep=time.sleep):
    app = payload.get("application_id")
    target = payload["target"]
    if app is not None and not re.fullmatch(r"application_[0-9]+_[0-9]+", app):
        raise ValueError("Invalid YARN application.")
    parsed = urlsplit(target)
    if parsed.scheme != "gs" or parsed.query or parsed.fragment or "/flink/savepoints/" not in parsed.path:
        raise ValueError("Savepoints must use the protected deployment prefix.")
    job_name = payload.get("job_name")
    if job_name:
        if not re.fullmatch(r"food-analytics-[0-9a-f]{20}", job_name):
            raise ValueError("Invalid expected YARN application name.")
        with urlopen("http://127.0.0.1:8088/ws/v1/cluster/apps?states=RUNNING", timeout=20) as response:
            listed = json.loads(response.read())
        matches = [row for row in (listed.get("apps") or {}).get("app", []) if row.get("name") == job_name]
        if len(matches) != 1 or not re.fullmatch(r"application_[0-9]+_[0-9]+", matches[0].get("id", "")):
            raise ValueError("Expected exactly one matching YARN application.")
        if app is not None and app != matches[0]["id"]:
            raise ValueError("YARN application identity changed.")
        app = matches[0]["id"]
    if not app:
        raise ValueError("YARN application was not identified.")
    base = "http://127.0.0.1:8088/proxy/" + app
    def http(path, method="GET", body=None):
        raw = None if body is None else json.dumps(body).encode()
        req = Request(base + path, data=raw, method=method, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=20) as result:
            return json.loads(result.read())
    request = request or http
    overview = request("/jobs/overview")
    active = [row for row in overview.get("jobs", []) if row.get("state") == "RUNNING"]
    if len(active) != 1 or not re.fullmatch(r"[0-9a-f]{32}", active[0].get("jid", "")):
        raise ValueError("Expected exactly one running Flink job in the selected YARN application.")
    job_id = active[0]["jid"]
    # No drain: retain pending event-time windows rather than emit a maximum watermark.
    trigger = request("/jobs/" + job_id + "/stop", "POST",
                      {"drain": False, "targetDirectory": target, "formatType": "CANONICAL"})
    identity = trigger.get("request-id", "")
    if not re.fullmatch(r"[0-9a-f]{32}", identity):
        raise ValueError("Flink did not return a valid savepoint operation.")
    deadline = clock() + 600
    while clock() < deadline:
        result = request("/jobs/" + job_id + "/savepoints/" + identity)
        if result.get("status", {}).get("id") == "COMPLETED":
            operation = result.get("operation", {})
            if operation.get("failure-cause"):
                raise RuntimeError("Flink savepoint failed.")
            uri = operation.get("location", "")
            if not uri.startswith(target.rstrip("/") + "/savepoint-") or "?" in uri or "#" in uri:
                raise ValueError("Flink returned a savepoint outside the approved prefix.")
            return {"savepoint_uri": uri, "flink_job_id": job_id, "application_id": app}
        sleep(3)
    raise RuntimeError("Savepoint timed out; retain the cluster and inspect the pause journal.")

def main():
    try:
        payload = json.loads(base64.b64decode(sys.argv[1], validate=True))
        print(json.dumps(stop(payload)), flush=True)
    except Exception:
        raise SystemExit("Flink stop-with-savepoint was not confirmed; no provider payload was printed.")

if __name__ == "__main__":
    main()
