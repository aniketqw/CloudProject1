"""Submit/reconcile one Restaurant Flink run; lifecycle resumes preserve savepoint identity."""
import hashlib
import json
import os
import re
import sys
import time

TERMINAL = {"DONE", "ERROR", "CANCELLED", "ATTEMPT_FAILURE"}

def release_key(env):
    settings = {key: env[key] for key in ("PROJECT_ID", "REGION", "DATAPROC_CLUSTER",
        "KAFKA_BOOTSTRAP_SERVERS", "KAFKA_SECRET_VERSION", "ANALYTICS_CHECKPOINT_URI",
        "ANALYTICS_JAR_URI", "ANALYTICS_RELEASE")}
    return hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()

def spec(env):
    from deploy.lifecycle_state import gs_parts
    project, region, cluster = (env[k] for k in ("PROJECT_ID", "REGION", "DATAPROC_CLUSTER"))
    if (not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project)
            or not re.fullmatch(r"[a-z]+-[a-z]+[0-9]", region)
            or not re.fullmatch(r"[a-z][a-z0-9-]{2,49}-flink", cluster)):
        raise ValueError("Invalid managed job destination.")
    prefix = cluster[:-6]
    if not re.fullmatch(r"[A-Za-z0-9.-]+:9092", env["KAFKA_BOOTSTRAP_SERVERS"]):
        raise ValueError("Kafka requires a credential-free broker endpoint.")
    expected_secret = "projects/" + project + "/secrets/" + prefix + "-kafka/versions/"
    if not env["KAFKA_SECRET_VERSION"].startswith(expected_secret) or not re.fullmatch(r"[1-9][0-9]*", env["KAFKA_SECRET_VERSION"][len(expected_secret):]):
        raise ValueError("Kafka credentials must use this deployment's pinned Secret Manager version reference.")
    settings = {"APP_ENV": "cloud", "KAFKA_BOOTSTRAP_SERVERS": env["KAFKA_BOOTSTRAP_SERVERS"],
        "KAFKA_SECRET_VERSION": env["KAFKA_SECRET_VERSION"],
        "ANALYTICS_CHECKPOINT_URI": env["ANALYTICS_CHECKPOINT_URI"], "ANALYTICS_WINDOW_SECONDS": "60"}
    gs_parts(env["ANALYTICS_JAR_URI"])
    gs_parts(settings["ANALYTICS_CHECKPOINT_URI"])
    run_id = env.get("ANALYTICS_RUN_ID", "")
    if run_id and not re.fullmatch(r"[a-f0-9]{32}", run_id):
        raise ValueError("Invalid analytics resume identity.")
    savepoint = env.get("ANALYTICS_SAVEPOINT", "")
    if savepoint:
        gs_parts(savepoint)
        checkpoint_root = settings["ANALYTICS_CHECKPOINT_URI"].rstrip("/")
        owned_savepoint = savepoint.startswith(checkpoint_root + "/savepoints/")
        owned_checkpoint = re.fullmatch(re.escape(checkpoint_root) + r"/[0-9a-f]{32}/chk-[1-9][0-9]*", savepoint)
        if not owned_savepoint and not owned_checkpoint:
            raise ValueError("Restore only from this deployment's protected savepoint or completed-checkpoint prefix.")
    release = release_key(env)
    digest = hashlib.sha256(json.dumps([release, run_id, savepoint]).encode()).hexdigest()[:20]
    job = {"reference": {"projectId": project, "jobId": "food-analytics-" + digest},
        "placement": {"clusterName": cluster},
        "labels": {"food_component": "restaurant-analytics", "food_release": release[:20], "food_protocol": "1"},
        "flinkJob": {"mainClass": "org.fooddelivery.analytics.RestaurantAnalytics",
            "jarFileUris": [env["ANALYTICS_JAR_URI"]],
            "args": ["--settings-json=" + json.dumps(settings, separators=(",", ":"))],
            "properties": {"parallelism.default": "1", "execution.checkpointing.interval": "10s",
                           "jobmanager.memory.process.size": "768m",
                           "taskmanager.memory.process.size": "1024m",
                           "taskmanager.memory.managed.fraction": "0.2",
                           "env.java.default-opts.client": "-Xms64m -Xmx256m",
                           # Kafka types cross the parent-loaded Flink connector API.
                           # Resolve them in the same loader on Dataproc application mode.
                           "classloader.parent-first-patterns.additional": "org.apache.kafka.",
                           "yarn.application.name": "food-analytics-" + digest}}}
    if savepoint:
        job["flinkJob"]["savepointUri"] = savepoint
    return project, region, job

def controlled_environment(env, store=None):
    """Every GitOps hook consults the same run record as the operator."""
    from deploy.lifecycle_state import GCSStore, LifecycleError, locations, read_control
    if not env.get("ANALYTICS_CONTROL_URI"):
        return dict(env)
    config = {"project_id": env["PROJECT_ID"], "region": env["REGION"],
              "zone": env["DEPLOYMENT_ZONE"], "prefix": env["DATAPROC_CLUSTER"][:-6]}
    if env["ANALYTICS_CONTROL_URI"] != locations(config)["control"]:
        raise LifecycleError("Analytics control URI must belong to this deployment.")
    record, _ = read_control(store or GCSStore(config), config, release_key(env))
    if not record:
        return dict(env)
    if record.get("mode") != "running":
        raise LifecycleError("Analytics is paused or not ready for submission.")
    if record.get("run_id") and not re.fullmatch(r"[a-f0-9]{32}", record["run_id"]):
        raise LifecycleError("Analytics run control is malformed.")
    return {**env, "ANALYTICS_RUN_ID": record["run_id"],
            "ANALYTICS_SAVEPOINT": record.get("savepoint_uri", "")}

def submit(session, env):
    project, region, job = spec(env)
    base = f"https://dataproc.googleapis.com/v1/projects/{project}/regions/{region}/jobs"
    identity = job["reference"]["jobId"]
    response = session.get(base + "/" + identity, timeout=15)
    if response.status_code == 200:
        actual = response.json()
        if actual.get("status", {}).get("state") in TERMINAL:
            raise RuntimeError("The run is terminal. Use lifecycle recovery or an explicit savepoint migration.")
        if actual.get("placement", {}).get("clusterName", env["DATAPROC_CLUSTER"]) != env["DATAPROC_CLUSTER"]:
            raise RuntimeError("Managed run belongs to another cluster.")
        return identity, "existing"
    if response.status_code != 404:
        raise RuntimeError("Managed job lookup failed.")
    existing = session.get(base, params={"filter": "labels.food_component=restaurant-analytics",
        "clusterName": env["DATAPROC_CLUSTER"], "pageSize": 100}, timeout=15)
    if existing.status_code != 200:
        raise RuntimeError("Managed job enumeration failed.")
    rows = existing.json()
    if rows.get("nextPageToken"):
        raise RuntimeError("Job history needs explicit review before creating another run.")
    if any(row.get("placement", {}).get("clusterName", env["DATAPROC_CLUSTER"]) == env["DATAPROC_CLUSTER"]
           and row.get("status", {}).get("state") not in TERMINAL for row in rows.get("jobs", [])):
        raise RuntimeError("Another analytics run is active. Savepoint and stop it before changing the run.")
    response = session.post(base + ":submit", json={"job": job}, timeout=30)
    if response.status_code not in {200, 201, 409}:
        raise RuntimeError("Managed Flink submission was not confirmed.")
    if response.status_code == 409:
        actual = session.get(base + "/" + identity, timeout=15)
        if actual.status_code != 200 or actual.json().get("status", {}).get("state") in TERMINAL:
            raise RuntimeError("Conflicting submission was not an active matching run.")
    return identity, "submitted"

def main():
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        env = controlled_environment(os.environ)
        credential, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = AuthorizedSession(credential)
        identity, outcome = submit(session, env)
        project, region, _ = spec(env)
        for _ in range(90):
            response = session.get(f"https://dataproc.googleapis.com/v1/projects/{project}/regions/{region}/jobs/{identity}", timeout=15)
            if response.status_code == 200:
                state = response.json().get("status", {}).get("state")
                if state == "RUNNING":
                    print(json.dumps({"service": "restaurant-analytics-launcher", "event": "managed_job_running", "outcome": outcome}))
                    return
                if state in TERMINAL:
                    raise RuntimeError("Analytics ended before readiness.")
            time.sleep(5)
        raise RuntimeError("Analytics readiness timed out.")
    except Exception:
        raise SystemExit("Managed analytics needs review. Provider responses and credentials were not printed.")

if __name__ == "__main__":
    main()
