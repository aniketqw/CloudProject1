"""Presentation lifecycle. Pause/resume default to an offline preview; --execute opts into cloud mutation."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys
import uuid
from datetime import datetime, timezone

from deploy.capacity import selected
from deploy.configure import ROOT, validate
from deploy.dataproc_submit import TERMINAL, release_key, spec
from deploy.lifecycle_state import (Journal, LifecycleError, GCSStore, context_key,
                                     destination, locations, read_control)

PAUSE_STEPS = ["suspend GitOps reconciliation", "disable node autoscaling",
    "stop web requests and application workloads", "stop analytics with a durable GCS savepoint",
    "stop managed analytics VMs", "resize the application pool to zero", "stop Cloud SQL",
    "verify all expected stopped states"]
RESUME_STEPS = ["verify deployment identity and the recorded release", "start Cloud SQL",
    "start managed analytics VMs", "restore the saved Flink state using a new stable run identity",
    "restore application nodes and replicas", "verify APIs and ZooKeeper readiness",
    "restore autoscaling and GitOps reconciliation", "verify GitOps and the analytics run"]

class Engine:
    def __init__(self, config, store, cloud, clock=None):
        self.config, self.store, self.cloud = config, store, cloud
        self.journal = Journal(store, config, **({"clock": clock} if clock else {}))
        self.cloud.pulse = lambda: self.journal.heartbeat() if self.journal.owner else None

    def step(self, key, action):
        if key not in self.journal.value["completed"]:
            self.journal.heartbeat()
            result = action()
            self.journal.value["completed"].append(key)
            self.journal.persist()
            return result

    def control(self, mode, run_id=None, savepoint=None):
        key = self.journal.value["snapshot"]["release_key"]
        old, generation = read_control(self.store, self.config, key)
        record = {"schema_version": 1, "context_key": context_key(self.config),
                  "release_key": key, "mode": mode,
                  "run_id": run_id if run_id is not None else (old or {}).get("run_id", ""),
                  "savepoint_uri": savepoint if savepoint is not None else (old or {}).get("savepoint_uri", "")}
        self.store.write("control", record, generation)

    def pause(self, recover=False):
        j = self.journal
        j.acquire("pause", recover)
        try:
            if j.value["phase"] == "paused":
                self.cloud.validate_snapshot(j.value["snapshot"])
                self.cloud.assert_paused()
                return
            if j.value["phase"] == "running":
                snapshot = self.cloud.snapshot()
                j.value.update(phase="pausing", snapshot=snapshot, pause_id=uuid.uuid4().hex,
                               completed=[], safe_resume_before=j.clock() + (snapshot["kafka_retention_days"] - 1) * 86400,
                               savepoint_uri=None, resume_run_id=None,
                               resume_job_id=None, savepoint_requested=False)
                j.persist()
            if j.value["phase"] != "pausing":
                raise LifecycleError("A resume is unfinished. Complete it before starting another pause.")
            snapshot = j.value["snapshot"]
            self.cloud.validate_snapshot(snapshot)
            self.step("gitops_suspended", lambda: self.cloud.suspend_gitops(snapshot))
            self.step("analytics_submission_paused", lambda: self.control("paused"))
            self.step("autoscaling_disabled", lambda: self.cloud.autoscaling({"enabled": False}))
            self.step("workloads_stopped", lambda: self.cloud.scale_workloads({name: 0 for name in snapshot["deployments"]}))
            if not j.value.get("savepoint_uri"):
                j.value["savepoint_requested"] = True
                j.persist()
                target = locations(self.config)["savepoints"] + j.value["pause_id"]
                uri = self.cloud.stop_analytics(snapshot, target)
                if not uri.startswith(target + "/savepoint-") or not self.store.savepoint_exists(uri):
                    raise LifecycleError("Savepoint did not match the protected pause prefix.")
                j.value["savepoint_uri"] = uri
                j.persist()
            self.step("analytics_stopped", lambda: self.cloud.set_dataproc("stop"))
            self.step("quorum_stopped", lambda: self.cloud.set_zookeeper(0))
            self.step("nodes_stopped", lambda: self.cloud.resize(0))
            self.step("database_stopped", lambda: self.cloud.set_sql("NEVER"))
            self.cloud.assert_paused()
            j.value["phase"] = "paused"
            j.persist()
        except BaseException:
            j.release(error=True)
            raise
        finally:
            if j.owner:
                j.release()

    def resume(self, recover=False, retry_analytics=False):
        j = self.journal
        if not j.value or not j.value.get("snapshot"):
            raise LifecycleError("No recorded pause exists. Use the initial deployment workflow first.")
        j.acquire("resume", recover)
        try:
            if j.value["phase"] == "running":
                if retry_analytics:
                    raise LifecycleError("Retry is only supported for an unfinished resume; investigate an unexpected running-release failure.")
                self.cloud.validate_snapshot(j.value["snapshot"])
                self.cloud.readiness()
                self.cloud.gitops_readiness()
                return
            if j.value["phase"] not in {"paused", "pausing", "resuming"}:
                raise LifecycleError("Unexpected lifecycle phase.")
            self.cloud.validate_snapshot(j.value["snapshot"])
            if j.clock() >= j.value.get("safe_resume_before", 0):
                raise LifecycleError("The verified Kafka retention margin expired. Review source offsets and event recovery before resuming.")
            if j.value["phase"] != "resuming":
                # A pause interrupted after the stop request must first reconcile its durable result.
                if not j.value.get("savepoint_uri") and j.value.get("savepoint_requested"):
                    target = locations(self.config)["savepoints"] + j.value["pause_id"]
                    uri = self.store.recover_savepoint(target)
                    if not uri or self.cloud.job(j.value["snapshot"]["job_id"])["status"]["state"] not in TERMINAL:
                        raise LifecycleError("Savepoint completion is unresolved. Re-run pause before resuming.")
                    j.value["savepoint_uri"] = uri
                j.value.update(phase="resuming", completed=[])
                j.persist()
            snapshot = j.value["snapshot"]
            self.step("sql_started", lambda: self.cloud.set_sql("ALWAYS"))
            self.step("dataproc_started", lambda: self.cloud.set_dataproc("start"))
            point = j.value.get("savepoint_uri")
            if point:
                if not self.store.savepoint_exists(point):
                    raise LifecycleError("Recorded savepoint metadata is missing. No fresh-state fallback is allowed.")
                if retry_analytics:
                    previous = j.value.get("resume_job_id")
                    if not previous or self.cloud.job(previous)["status"]["state"] not in TERMINAL:
                        raise LifecycleError("Retry requires the exact prior resume job to be confirmed terminal.")
                    self.cloud.suspend_gitops(snapshot)
                    j.value["resume_run_id"] = None
                    j.value["completed"] = [v for v in j.value["completed"] if v not in {"analytics_started", "gitops_restored"}]
                if not j.value.get("resume_run_id"):
                    j.value["resume_run_id"] = uuid.uuid4().hex
                env = {**self.cloud.analytics_env(), "ANALYTICS_RUN_ID": j.value["resume_run_id"],
                       "ANALYTICS_SAVEPOINT": point}
                j.value["resume_job_id"] = spec(env)[2]["reference"]["jobId"]
                j.persist()
                self.control("running", j.value["resume_run_id"], point)
                self.step("analytics_started", lambda: self.cloud.start_analytics(j.value["resume_run_id"], point))
            else:
                # Undo a pause that failed before any stop request; reuse the active original run.
                if self.cloud.job(snapshot["job_id"])["status"]["state"] != "RUNNING":
                    raise LifecycleError("Original analytics is not active and no savepoint was recorded.")
                self.control("running")
            self.step("nodes_started", lambda: self.cloud.resize(snapshot["nodes"]))
            self.step("quorum_started", lambda: self.cloud.set_zookeeper(3))
            def restore_workloads():
                counts = dict(snapshot["deployments"])
                for name, workload in self.cloud.values["workloads"].items():
                    if workload.get("hpa"):
                        counts[name] = self.cloud.values["hpa"]["min"]
                self.cloud.scale_workloads(counts)
            self.step("workloads_started", restore_workloads)
            self.cloud.readiness()
            self.step("autoscaling_restored", lambda: self.cloud.autoscaling(snapshot["autoscaling"]))
            self.step("gitops_restored", lambda: self.cloud.restore_gitops(snapshot))
            self.cloud.gitops_readiness()
            identity = j.value.get("resume_job_id") or snapshot["job_id"]
            if self.cloud.job(identity)["status"]["state"] != "RUNNING":
                raise LifecycleError("Analytics stopped before final readiness.")
            j.value["phase"] = "running"
            j.value.setdefault("history", []).append({"pause_id": j.value["pause_id"], "result": "resumed"})
            j.value["history"] = j.value["history"][-20:]
            j.persist()
        except BaseException:
            j.release(error=True)
            raise
        finally:
            if j.owner:
                j.release()

def preview(config, action):
    profile, capacity = selected(config)
    return {"result": "PREVIEW_ONLY", "action": action, "compute_profile": profile,
            "capacity": {k: v for k, v in capacity.items() if k not in {"resources", "sql_proxy_resources"}},
            "steps": PAUSE_STEPS if action == "pause" else RESUME_STEPS,
            "cloud_requests": 0, "resources_deleted": False,
            "retained_charges": ["GKE control plane unless credited", "disks and database storage",
                                 "backups, buckets and registry", "retained networking", "Confluent usage"]}

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "check", "pause", "resume"])
    parser.add_argument("--config", default="deploy/config.team.json")
    parser.add_argument("--execute", action="store_true", help="Explicitly allow cloud pause/resume mutations.")
    parser.add_argument("--dry-run", action="store_true", help="Offline preview only; no cloud access.")
    parser.add_argument("--example", action="store_true", help="Use the public example for an offline preview.")
    parser.add_argument("--recover", action="store_true", help="Reclaim an expired lease after confirming the previous operator stopped.")
    parser.add_argument("--retry-analytics", action="store_true", help="During an unfinished resume, retry a confirmed terminal run from the same saved state.")
    args = parser.parse_args(argv)
    if args.execute and (args.dry_run or args.example or args.action not in {"pause", "resume"}):
        parser.error("--execute is only valid for pause/resume against a real configuration.")
    if args.retry_analytics and args.action != "resume":
        parser.error("--retry-analytics is only valid for resume.")
    try:
        config = validate(json.loads((ROOT/("deploy/config.example.json" if args.example else args.config)).read_text(encoding="utf-8")),
                          allow_example=args.example)
    except (OSError, ValueError):
        parser.error("Configuration is unavailable or invalid. Render the non-secret config; no values were printed.")
    if args.dry_run or args.example or (args.action in {"pause", "resume"} and not args.execute):
        print(json.dumps(preview(config, args.action), indent=2))
        return
    try:
        from deploy.lifecycle_cloud import Cloud
        values = json.loads((ROOT/"deploy/environments/team/food-values.json").read_text(encoding="utf-8"))
        if values.get("computeProfile") != config.get("compute_profile", "demo"):
            raise LifecycleError("Render and review configuration before using lifecycle commands.")
        store = GCSStore(config)
        cloud = Cloud(config, store, values)
        engine = Engine(config, store, cloud)
        if args.action == "status":
            actual = cloud.overview()
            print(json.dumps({"result": "OBSERVED", "phase": (engine.journal.value or {}).get("phase", "unrecorded"),
                "operation_in_progress": bool((engine.journal.value or {}).get("lock")),
                "retention_review_deadline_utc": datetime.fromtimestamp(engine.journal.value["safe_resume_before"], timezone.utc).isoformat() if engine.journal.value and engine.journal.value.get("safe_resume_before") else None,
                "application_nodes": actual["nodes"],
                "autoscaling_enabled": bool(actual["pool"].get("autoscaling", {}).get("enabled")),
                "sql_activation": actual["sql"]["settings"].get("activationPolicy"),
                "analytics_cluster": actual["dataproc"]["status"]["state"]}))
            return
        if args.action == "check":
            if engine.journal.value and engine.journal.value.get("phase") != "running":
                raise LifecycleError("Deployment is paused or unfinished. Resume before checking running readiness.")
            cloud.snapshot()
            cloud.readiness()
            cloud.gitops_readiness()
        elif args.action == "pause":
            engine.pause(args.recover)
        else:
            engine.resume(args.recover, args.retry_analytics)
        print(json.dumps({"result": "PASS", "action": args.action,
                         "phase": (engine.journal.value or {}).get("phase", "running"),
                         "resources_deleted": False,
                         "scope": "Lifecycle readiness; an end-to-end order and cloud load evidence remain separate checks."}))
    except LifecycleError as error:
        raise SystemExit(str(error))
    except Exception:
        raise SystemExit("Lifecycle operation failed. No credentials/provider payload were printed. Inspect status and authorized access before retrying.")

if __name__ == "__main__":
    main()
