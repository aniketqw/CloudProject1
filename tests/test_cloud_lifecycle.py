"""Failure/retry, concurrency, scope and capacity contracts; no cloud network."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deploy.capacity import PROFILES, selected
from deploy.configure import validate, render
from deploy.dataproc_submit import controlled_environment, release_key, spec, TERMINAL
from deploy.flink_control import application_id, stop
from deploy.lifecycle import Engine, main
from deploy.lifecycle_state import Journal, LifecycleError, context_key, guard_running, locations, gs_parts
from deploy import cloud_stage

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {**json.loads((ROOT/"deploy/config.example.json").read_text()), "project_id": "assignment-test-123",
    "prefix": "food", "public_host": "demo.assignment.test", "git_revision": "demo-release",
    "image_tag": "demo-release", "kafka_bootstrap": "broker.example.test:9092",
    "kafka_cluster_id": "lkc-test123", "kafka_rest_endpoint": "https://broker.example.test",
    "admin_cidr": "198.51.100.4/32", "state_bucket": "assignment-test-123-state"}
ENV = {"PROJECT_ID": CONFIG["project_id"], "REGION": CONFIG["region"], "DEPLOYMENT_ZONE": CONFIG["zone"],
    "DATAPROC_CLUSTER": "food-flink", "KAFKA_BOOTSTRAP_SERVERS": CONFIG["kafka_bootstrap"],
    "KAFKA_SECRET_VERSION": "projects/assignment-test-123/secrets/food-kafka/versions/1",
    "ANALYTICS_CHECKPOINT_URI": "gs://assignment-test-123-food-checkpoints/flink",
    "ANALYTICS_JAR_URI": "gs://assignment-test-123-food-artifacts/restaurant-demo-release.jar",
    "ANALYTICS_RELEASE": "demo-release", "ANALYTICS_CONTROL_URI": locations(CONFIG)["control"]}

class Store:
    def __init__(self):
        self.rows = {}
        self.generations = {}
        self.points = set()
    def read(self, kind):
        return copy.deepcopy(self.rows.get(kind)), self.generations.get(kind, 0)
    def write(self, kind, value, generation):
        if self.generations.get(kind, 0) != generation:
            raise LifecycleError("Generation conflict")
        self.generations[kind] = generation + 1
        self.rows[kind] = copy.deepcopy(value)
        return generation + 1
    def savepoint_exists(self, uri):
        return uri in self.points
    def recover_savepoint(self, prefix):
        found = [v for v in self.points if v.startswith(prefix + "/")]
        if len(found) > 1:
            raise LifecycleError("Ambiguous savepoint")
        return found[0] if found else None

class FakeCloud:
    """External state, including a failed response after the action actually succeeded."""
    def __init__(self, store):
        self.store = store
        self.events = []
        self.fail_after = None
        self.nodes, self.zk = 2, 3
        self.sql, self.dp = "ALWAYS", "RUNNING"
        self.auto = {"enabled": True, "minNodeCount": 2, "maxNodeCount": 2}
        self.apps = {"web-ui": 1, "customer-service": 5, "worker": 2}
        self.values = {"image": "verified-image", "hpa": {"min": 1},
                       "workloads": {"web-ui": {}, "customer-service": {"hpa": True}, "worker": {}}}
        self.original = spec(ENV)[2]["reference"]["jobId"]
        self.jobs = {self.original: {"status": {"state": "RUNNING"}}}
        self.created_runs = set()
        self.gitops, self.release_changed = True, False
        self.snapshot_count = 0
        self.pulse = lambda: None
    def effect(self, name):
        self.events.append(name)
        if self.fail_after == name:
            self.fail_after = None
            raise LifecycleError("Injected lost response after " + name)
    def snapshot(self):
        self.snapshot_count += 1
        return {"kafka_retention_days": 21, "profile": "demo", "image": self.values["image"], "release_key": release_key(ENV),
                "nodes": self.nodes, "autoscaling": copy.deepcopy(self.auto), "deployments": dict(self.apps),
                "argo": {}, "job_id": self.original, "application_id": "application_123_0001"}
    def validate_snapshot(self, snapshot):
        if self.release_changed:
            raise LifecycleError("release changed")
    def analytics_env(self):
        return dict(ENV)
    def suspend_gitops(self, snapshot):
        self.gitops = False
        self.effect("gitops_off")
    def restore_gitops(self, snapshot):
        assert all(self.apps.values()) and self.zk == 3 and self.nodes == 2
        self.gitops = True
        self.effect("gitops_on")
    def autoscaling(self, value):
        self.auto = dict(value)
        self.effect("autoscaling_on" if value["enabled"] else "autoscaling_off")
    def scale_workloads(self, counts):
        if any(counts.values()):
            assert self.sql == "ALWAYS" and self.dp == "RUNNING" and self.nodes == 2 and self.zk == 3
        else:
            assert not self.gitops and not self.auto["enabled"]
        self.apps = dict(counts)
        self.effect("apps_on" if any(counts.values()) else "apps_off")
    def stop_analytics(self, snapshot, target):
        assert not any(self.apps.values())
        recovered = self.store.recover_savepoint(target)
        if recovered:
            return recovered
        point = target + "/savepoint-abc-def"
        self.store.points.add(point)
        self.jobs[self.original]["status"]["state"] = "DONE"
        self.effect("savepoint")
        return point
    def set_dataproc(self, action):
        if action == "stop":
            assert self.store.points and not any(self.apps.values())
        self.dp = "RUNNING" if action == "start" else "STOPPED"
        self.effect("dp_" + action)
    def resize(self, count):
        if count == 0:
            assert self.zk == 0 and not any(self.apps.values()) and self.dp == "STOPPED" and not self.auto["enabled"]
        self.nodes = count
        self.effect("nodes_on" if count else "nodes_off")
    def set_zookeeper(self, count):
        if count:
            assert self.nodes == 2
        else:
            assert not any(self.apps.values())
        self.zk = count
        self.effect("zk_on" if count else "zk_off")
    def set_sql(self, value):
        if value == "NEVER":
            assert self.nodes == 0 and self.dp == "STOPPED" and not any(self.apps.values())
        self.sql = value
        self.effect("sql_on" if value == "ALWAYS" else "sql_off")
    def job(self, identity):
        return copy.deepcopy(self.jobs[identity])
    def start_analytics(self, run_id, point):
        assert self.sql == "ALWAYS" and self.dp == "RUNNING" and point in self.store.points
        identity = spec({**ENV, "ANALYTICS_RUN_ID": run_id, "ANALYTICS_SAVEPOINT": point})[2]["reference"]["jobId"]
        if identity in self.jobs and self.jobs[identity]["status"]["state"] in TERMINAL:
            raise LifecycleError("terminal resume run")
        self.created_runs.add(identity)
        self.jobs[identity] = {"status": {"state": "RUNNING"}}
        self.effect("analytics_on")
        return identity
    def readiness(self):
        assert all(self.apps.values()) and self.zk == 3 and self.nodes == 2
        self.effect("ready")
    def gitops_readiness(self):
        assert self.gitops
        self.effect("gitops_ready")
    def assert_paused(self):
        assert self.nodes == 0 and self.zk == 0 and self.dp == "STOPPED" and self.sql == "NEVER"
        assert not self.gitops and not self.auto["enabled"]
        self.effect("paused")

class Lifecycle(unittest.TestCase):
    def setup(self):
        store = Store()
        return store, FakeCloud(store)
    def test_complete_cycle_preserves_state_and_hpa_starts_at_minimum(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        self.assertEqual(store.rows["journal"]["phase"], "paused")
        self.assertEqual(store.rows["control"]["mode"], "paused")
        Engine(CONFIG, store, cloud).resume()
        self.assertEqual(store.rows["journal"]["phase"], "running")
        self.assertEqual(cloud.apps["customer-service"], 1)
        self.assertEqual(cloud.apps["worker"], 2)
        self.assertEqual(len(cloud.created_runs), 1)
        self.assertEqual(len(store.points), 1)
        self.assertLess(cloud.events.index("savepoint"), cloud.events.index("sql_off"))
        self.assertLess(cloud.events.index("zk_on"), cloud.events.index("apps_on"))
        resumed = controlled_environment(ENV, store)
        self.assertEqual(spec(resumed)[2]["reference"]["jobId"], next(iter(cloud.created_runs)))
    def test_lost_pause_responses_can_be_retried_without_new_savepoint(self):
        for failure in ["gitops_off", "autoscaling_off", "apps_off", "savepoint", "dp_stop", "zk_off", "nodes_off", "sql_off", "paused"]:
            with self.subTest(failure=failure):
                store, cloud = self.setup()
                cloud.fail_after = failure
                with self.assertRaises(LifecycleError):
                    Engine(CONFIG, store, cloud).pause()
                Engine(CONFIG, store, cloud).pause()
                self.assertEqual(store.rows["journal"]["phase"], "paused")
                self.assertEqual(len(store.points), 1)
                self.assertEqual(cloud.snapshot_count, 1)
                self.assertIsNone(store.rows["journal"]["lock"])
    def test_lost_resume_responses_reuse_one_restore_identity(self):
        for failure in ["sql_on", "dp_start", "analytics_on", "nodes_on", "zk_on", "apps_on", "ready", "autoscaling_on", "gitops_on", "gitops_ready"]:
            with self.subTest(failure=failure):
                store, cloud = self.setup()
                Engine(CONFIG, store, cloud).pause()
                cloud.fail_after = failure
                with self.assertRaises(LifecycleError):
                    Engine(CONFIG, store, cloud).resume()
                Engine(CONFIG, store, cloud).resume()
                self.assertEqual(store.rows["journal"]["phase"], "running")
                self.assertEqual(len(cloud.created_runs), 1)
    def test_repeated_commands_are_idempotent(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        Engine(CONFIG, store, cloud).pause()
        Engine(CONFIG, store, cloud).resume()
        Engine(CONFIG, store, cloud).resume()
        self.assertEqual(len(cloud.created_runs), 1)
        self.assertEqual(len(store.points), 1)
    def test_two_cycles_have_distinct_runtime_ids_and_savepoints(self):
        store, cloud = self.setup()
        for _ in range(2):
            if cloud.created_runs:
                cloud.original = next(v for v in cloud.created_runs if cloud.jobs[v]["status"]["state"] == "RUNNING")
            Engine(CONFIG, store, cloud).pause()
            Engine(CONFIG, store, cloud).resume()
        self.assertEqual(len(store.points), 2)
        self.assertEqual(len(cloud.created_runs), 2)
    def test_missing_state_changed_release_or_no_pause_fails_closed(self):
        store, cloud = self.setup()
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        Engine(CONFIG, store, cloud).pause()
        cloud.release_changed = True
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        cloud.release_changed = False
        store.points.clear()
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        self.assertFalse(cloud.created_runs)
    def test_expired_retention_window_refuses_resume_before_mutation(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        record, generation = store.read("journal")
        record["safe_resume_before"] = 1
        store.write("journal", record, generation)
        before = list(cloud.events)
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        self.assertEqual(cloud.events, before)
    def test_terminal_resume_retry_requires_flag_and_retains_savepoint(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        cloud.fail_after = "analytics_on"
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        first = next(iter(cloud.created_runs))
        cloud.jobs[first]["status"]["state"] = "ERROR"
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        Engine(CONFIG, store, cloud).resume(retry_analytics=True)
        self.assertEqual(len(cloud.created_runs), 2)
        self.assertEqual(len(store.points), 1)
    def test_terminal_failure_after_gitops_restore_can_be_retried_safely(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        cloud.fail_after = "gitops_ready"
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).resume()
        first = next(iter(cloud.created_runs))
        cloud.jobs[first]["status"]["state"] = "ERROR"
        Engine(CONFIG, store, cloud).resume(retry_analytics=True)
        self.assertTrue(cloud.gitops)
        self.assertEqual(len(cloud.created_runs), 2)
    def test_undo_partial_pause_before_savepoint_request(self):
        store, cloud = self.setup()
        cloud.fail_after = "apps_off"
        with self.assertRaises(LifecycleError):
            Engine(CONFIG, store, cloud).pause()
        Engine(CONFIG, store, cloud).resume()
        self.assertFalse(cloud.created_runs)
        self.assertEqual(spec(controlled_environment(ENV, store))[2]["reference"]["jobId"], cloud.original)
    def test_active_lease_and_stale_generations_prevent_interleaved_operations(self):
        store = Store()
        first = Journal(store, CONFIG, clock=lambda: 100)
        second = Journal(store, CONFIG, clock=lambda: 100)
        first.acquire("pause")
        with self.assertRaises(LifecycleError):
            second.acquire("resume")
        with self.assertRaises(LifecycleError):
            Journal(store, CONFIG, clock=lambda: 101).acquire("resume", recover=True)
        expired = Journal(store, CONFIG, clock=lambda: 2000)
        with self.assertRaises(LifecycleError):
            expired.acquire("pause")
        expired.acquire("pause", recover=True)
        with self.assertRaises(LifecycleError):
            first.heartbeat()
    def test_foreign_journal_and_paused_terraform_fail_closed(self):
        store, cloud = self.setup()
        Engine(CONFIG, store, cloud).pause()
        with self.assertRaises(LifecycleError):
            guard_running(CONFIG, store)
        with self.assertRaises(LifecycleError):
            Journal(store, {**CONFIG, "prefix": "other"})
        Engine(CONFIG, store, cloud).resume()
        guard_running(CONFIG, store)

class Configuration(unittest.TestCase):
    def test_demo_default_and_rejection_of_private_fields_and_unknown_profiles(self):
        old = dict(CONFIG);old.pop("compute_profile")
        self.assertEqual(selected(validate(old))[0], "demo")
        for change in [{"compute_profile": "tiny"}, {"compute_profile": True}, {"private_key": "synthetic"}]:
            with self.assertRaises((ValueError, TypeError)):
                validate({**CONFIG, **change})
    def test_renderer_preserves_secret_versions_and_required_redundancy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            import shutil
            for name in ["deploy/charts/food/values.yaml", "functions/notification_transport/main.py", "functions/notification_transport/requirements.txt"]:
                target = root/name;target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, target)
            with patch("deploy.configure.ROOT", root):
                output = render(CONFIG, outputs={"secret_versions": {"value": {"db-password": "7", "kafka": "8", "web-access": "9"}},
                    "kafka_secret_version": {"value": "projects/assignment-test-123/secrets/food-kafka/versions/8"}})
            values = json.loads((output/"food-values.json").read_text())
            variables = json.loads((root/".local-build/config/team/cloud.tfvars.json").read_text())
            self.assertEqual(values["computeProfile"], variables["compute_profile"])
            self.assertEqual(values["resources"], PROFILES["demo"]["resources"])
            self.assertEqual(values["managedFlink"]["env"]["ANALYTICS_CONTROL_URI"], locations(CONFIG)["control"])
            self.assertTrue(values["managedFlink"]["env"]["KAFKA_SECRET_VERSION"].endswith("/8"))
            self.assertEqual(values["workloads"]["task-scheduler"]["replicas"], 2)
            self.assertEqual(sum(bool(v.get("hpa")) for v in values["workloads"].values()), 2)
    def test_offline_preview_never_constructs_cloud_clients(self):
        for action in ("pause", "resume", "status", "check"):
            with patch("deploy.lifecycle.GCSStore", side_effect=AssertionError("Cloud access")), patch("sys.stdout", new_callable=io.StringIO) as out:
                main([action, "--dry-run", "--example"])
            self.assertEqual(json.loads(out.getvalue())["cloud_requests"], 0)
        with patch("sys.stderr", new_callable=io.StringIO), self.assertRaises(SystemExit):
            main(["pause", "--execute", "--example"])
    def test_shared_profile_source_and_persistent_volume_retention(self):
        terraform = json.loads((ROOT/"deploy/terraform/cloud/main.tf.json").read_text())
        self.assertEqual(terraform["variable"]["compute_profile"]["default"], "demo")
        self.assertIn("../../profiles.json", terraform["locals"]["profiles"])
        r = terraform["resource"]
        self.assertEqual(r["google_container_node_pool"]["apps"]["autoscaling"]["max_node_count"], "$"+"{local.capacity.gke_max_nodes}")
        self.assertEqual(r["google_dataproc_cluster"]["flink"]["cluster_config"]["worker_config"]["num_instances"], "$"+"{local.capacity.flink_workers}")
        self.assertTrue(r["google_sql_database_instance"]["database"]["deletion_protection"])
        self.assertIn("whenScaled: Retain", (ROOT/"deploy/charts/food/templates/zookeeper.yaml").read_text())
    def test_plan_receipt_detects_input_changes_without_storing_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root/"deploy/terraform/cloud";folder.mkdir(parents=True)
            (root/"deploy/profiles.json").write_text("{}")
            config = root/"config.json";config.write_text("{}")
            variables = root/"variables.json";variables.write_text("{}")
            private = folder/"secrets.auto.tfvars.json";private.write_text('{"marker":"synthetic-private"}')
            with patch("deploy.cloud_stage.ROOT", root):
                first = cloud_stage.plan_inputs(config, folder, variables, None)
                private.write_text('{"marker":"synthetic-private-changed"}')
                second = cloud_stage.plan_inputs(config, folder, variables, None)
            self.assertNotEqual(first, second)
            self.assertNotIn("synthetic-private", json.dumps(second))

class DatabasePools(unittest.TestCase):
    def test_local_and_sqlite_defaults_stay_compatible(self):
        from common.database_options import engine_options
        original = {"pool_pre_ping": True, "hide_parameters": True}
        self.assertEqual(engine_options("mysql+pymysql://synthetic", original, {}), original)
        self.assertEqual(engine_options("sqlite://", original, {"DB_POOL_SIZE": "1"}), original)
    def test_small_cloud_pool_is_bounded_and_never_echoes_values(self):
        from common.database_options import engine_options
        options = engine_options("mysql+pymysql://synthetic", environ={"DB_POOL_SIZE": "2", "DB_MAX_OVERFLOW": "0"})
        self.assertEqual(options["pool_size"], 2)
        self.assertEqual(options["max_overflow"], 0)
        for key, value in [("DB_POOL_SIZE", "99"), ("DB_POOL_SIZE", "synthetic-private-marker"), ("DB_MAX_OVERFLOW", "9")]:
            with self.assertRaises(ValueError) as error:
                engine_options("mysql+pymysql://synthetic", environ={key: value})
            self.assertNotIn(value, str(error.exception))
    def test_every_sql_factory_uses_the_shared_pool_policy(self):
        for name in ("customer_service/customer_service.py", "order_service/storage.py", "task_scheduler/storage.py"):
            source = (ROOT/name).read_text()
            self.assertLess(source.index('= engine_options('), source.index('db.init_app(app)'))

class SourceExport(unittest.TestCase):
    def test_only_requested_markdown_and_public_configuration_are_exported(self):
        from deploy import export_handoff
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ["CLOUD_DEPLOYMENT_HANDOFF.md", "AGENTS.md", "PRIVATE_NOTES.md", "docs/internal.md", "deploy/profiles.json", "deploy/config.team.json", "deploy/secrets.json", "deploy/config.example.json", "common/database_options.py"]
            for name in names:
                path = root/name;path.parent.mkdir(parents=True, exist_ok=True);path.write_text("synthetic")
            with patch("deploy.export_handoff.ROOT", root):
                exported = {str(p.relative_to(root)).replace(chr(92), "/") for p in export_handoff.candidates()}
            self.assertEqual(exported, {"CLOUD_DEPLOYMENT_HANDOFF.md", "deploy/profiles.json", "deploy/config.example.json", "common/database_options.py"})
    def test_export_rejects_all_private_key_header_types(self):
        from deploy.export_handoff import verify
        for kind in (b"", b"RSA ", b"EC ", b"OPENSSH ", b"ENCRYPTED "):
            value = b"-----BEGIN " + kind + b"PRIVATE KEY-----"
            with self.assertRaises(ValueError):
                verify([("synthetic.txt", value)])

class AnalyticsProtocol(unittest.TestCase):
    def test_resume_identity_is_stable_and_bound_to_its_savepoint(self):
        point = locations(CONFIG)["savepoints"] + "manual/savepoint-test"
        env = {**ENV, "ANALYTICS_RUN_ID": "a"*32, "ANALYTICS_SAVEPOINT": point}
        self.assertEqual(spec(env), spec(dict(env)))
        for changed in [{**env, "ANALYTICS_RUN_ID": "b"*32}, {**env, "ANALYTICS_SAVEPOINT": point+"-changed"}]:
            self.assertNotEqual(spec(env)[2]["reference"], spec(changed)[2]["reference"])
        for uri in ["https://example.test/state", "gs://other-bucket/savepoint-test"]:
            with self.assertRaises((ValueError, LifecycleError)):
                spec({**env, "ANALYTICS_SAVEPOINT": uri})
    def test_paused_or_foreign_release_control_never_starts_fresh_job(self):
        store = Store()
        record = {"schema_version": 1, "context_key": context_key(CONFIG), "release_key": release_key(ENV),
                  "mode": "paused", "run_id": "a"*32, "savepoint_uri": ""}
        store.write("control", record, 0)
        with self.assertRaises(LifecycleError):
            controlled_environment(ENV, store)
        record["mode"] = "running";record["release_key"] = "another"
        store.write("control", record, 1)
        with self.assertRaises(LifecycleError):
            controlled_environment(ENV, store)
    def test_raw_kafka_credentials_never_enter_a_managed_job_argument(self):
        for changed in [{"KAFKA_SECRET_VERSION": "synthetic-private-marker"},
                        {"KAFKA_SECRET_VERSION": "projects/other-project/secrets/food-kafka/versions/1"},
                        {"KAFKA_BOOTSTRAP_SERVERS": "user:synthetic-private-marker@broker:9092"}]:
            with self.assertRaises(ValueError) as error:
                spec({**ENV, **changed})
            self.assertNotIn("synthetic-private-marker", str(error.exception))
    def test_yarn_discovery_never_guesses_between_applications(self):
        job = {"yarnApplications": [{"name": "Restaurant analytics", "state": "RUNNING",
                                    "trackingUrl": "http://private:8088/proxy/application_123_0001/"}]}
        self.assertEqual(application_id(job), "application_123_0001")
        job["yarnApplications"].append({"state": "RUNNING", "name": "application_456_0001"})
        with self.assertRaises(ValueError):
            application_id(job)
    def test_stop_preserves_pending_windows_and_waits_for_result(self):
        calls = []
        responses = iter([{"jobs": [{"jid": "a"*32, "state": "RUNNING"}]},
                          {"request-id": "b"*32}, {"status": {"id": "IN_PROGRESS"}},
                          {"status": {"id": "COMPLETED"}, "operation": {"location": locations(CONFIG)["savepoints"]+"pause/savepoint-safe"}}])
        def request(path, method="GET", body=None):
            calls.append((path, method, body));return next(responses)
        value = stop({"application_id": "application_123_0001", "target": locations(CONFIG)["savepoints"]+"pause"},
                     request=request, sleep=lambda _: None)
        self.assertTrue(value["savepoint_uri"].endswith("savepoint-safe"))
        self.assertFalse(calls[1][2]["drain"])
        self.assertEqual(calls[1][2]["formatType"], "CANONICAL")
    def test_failed_or_foreign_savepoints_are_rejected(self):
        for operation in [{"failure-cause": {"message": "synthetic"}}, {"location": "gs://another-bucket/savepoint-outside"}]:
            responses = iter([{"jobs": [{"jid": "a"*32, "state": "RUNNING"}]}, {"request-id": "b"*32},
                              {"status": {"id": "COMPLETED"}, "operation": operation}])
            with self.assertRaises((RuntimeError, ValueError)):
                stop({"application_id": "application_123_0001", "target": locations(CONFIG)["savepoints"]+"pause"},
                     request=lambda *args: next(responses))
    def test_storage_destinations_reject_credentials_traversal_and_queries(self):
        for uri in ["gs://bucket/key?token=synthetic", "gs://user:synthetic@bucket/key", "gs://bucket/a/../b", "file:///tmp/state"]:
            with self.assertRaises(LifecycleError):
                gs_parts(uri)

if __name__ == "__main__":
    unittest.main()
