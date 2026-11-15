"""Adapter contract tests for real API shapes and strict deployment scope."""
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from deploy.lifecycle_cloud import Cloud
from deploy.lifecycle import Engine
from deploy.lifecycle_state import LifecycleError, locations, context_key
from deploy.dataproc_submit import spec
from deploy.flink_control import stop
from deploy import cloud_stage
from tests.test_cloud_lifecycle import CONFIG, ENV, Store

def fixture():
    values = {"image": "verified-image", "env": dict(ENV), "managedFlink": {"env": {}},
              "workloads": {"customer-service": {"hpa": True}, "order-service": {"hpa": True}},
              "hpa": {"min": 1}}
    cloud = Cloud(CONFIG, Store(), values, session=Mock())
    cloud.store.write("kafka_policy", {"schema_version": 1, "context_key": context_key(CONFIG),
        "retention_days": 21, "cluster_id": CONFIG["kafka_cluster_id"], "broker": CONFIG["kafka_bootstrap"]}, 0)
    actual = {"gke": {"status": "RUNNING", "endpoint": "192.0.2.10", "createTime": "created-gke"},
              "pool": {"config": {"machineType": "e2-standard-2"}, "autoscaling": {"enabled": True, "minNodeCount": 2, "maxNodeCount": 2},
                       "instanceGroupUrls": ["https://www.googleapis.com/compute/v1/projects/assignment-test-123/zones/asia-south1-a/instanceGroups/expected-group"]},
              "nodes": 2, "sql": {"createTime": "created-sql", "settings": {"tier": "db-g1-small", "activationPolicy": "ALWAYS"}},
              "dataproc": {"clusterUuid": "same-cluster", "status": {"state": "RUNNING"}}}
    job = spec(ENV)[2]
    job.update(status={"state": "RUNNING"}, yarnApplications=[{"state": "RUNNING", "name": "application_123_0001"}])
    cloud.overview = Mock(return_value=actual)
    cloud.jobs = Mock(return_value=[job])
    cloud.job = Mock(return_value=job)
    def kube(args, payload=None):
        if args[:2] == ["config", "view"]:
            return {"clusters": [{"cluster": {"server": "https://192.0.2.10"}}]}
        if args[:2] == ["get", "deployments"]:
            return {"items": [{"metadata": {"name": name}, "spec": {"replicas": 1, "template": {"spec": {"containers": [
                {"name": "application", "image": values["image"]}]}}}} for name in values["workloads"]]}
        if args[:2] == ["get", "hpa"]:
            return {"items": [{"metadata": {"name": name}, "spec": {"minReplicas": 1}} for name in values["workloads"]]}
        if args[:2] == ["get", "jobs"]:
            return {"items": []}
        if args[:2] == ["get", "statefulset"]:
            return {"spec": {"replicas": 3}, "status": {"readyReplicas": 3}}
        if args[:2] == ["get", "application"]:
            return {"spec": {"source": {"targetRevision": CONFIG["git_revision"]},
                             "syncPolicy": {"automated": {"prune": True, "selfHeal": True}}}}
        raise AssertionError("Unexpected Kubernetes request: " + repr(args))
    cloud.kubectl = Mock(side_effect=kube)
    return cloud, actual

class Adapter(unittest.TestCase):
    def test_snapshot_confirms_capacity_release_and_resource_identity(self):
        cloud, _ = fixture()
        snapshot = cloud.snapshot()
        self.assertEqual(snapshot["nodes"], 2)
        self.assertEqual(snapshot["application_id"], "application_123_0001")
        cloud.validate_snapshot(snapshot)

    def test_foreign_endpoint_unexpected_capacity_and_active_load_block_pause(self):
        for changed in ["endpoint", "capacity", "load", "image", "hpa", "quorum", "revision"]:
            with self.subTest(changed=changed):
                cloud, actual = fixture()
                original = cloud.kubectl.side_effect
                if changed == "capacity":
                    actual["nodes"] = 4
                else:
                    def kube(args, payload=None):
                        result = original(args, payload)
                        if changed == "endpoint" and args[:2] == ["config", "view"]:
                            result["clusters"][0]["cluster"]["server"] = "https://different.invalid"
                        elif changed == "load" and args[:2] == ["get", "jobs"]:
                            result["items"] = [{"status": {"active": 1}}]
                        elif changed == "image" and args[:2] == ["get", "deployments"]:
                            result["items"][0]["spec"]["template"]["spec"]["containers"][0]["image"] = "other-release"
                        elif changed == "hpa" and args[:2] == ["get", "hpa"]:
                            result["items"] = []
                        elif changed == "quorum" and args[:2] == ["get", "statefulset"]:
                            result["status"]["readyReplicas"] = 2
                        elif changed == "revision" and args[:2] == ["get", "application"]:
                            result["spec"]["source"]["targetRevision"] = "another-release"
                        return result
                    cloud.kubectl.side_effect = kube
                with self.assertRaises(LifecycleError):
                    cloud.snapshot()

    def test_recreated_resource_or_node_pool_cannot_use_stale_snapshot(self):
        cloud, actual = fixture()
        snapshot = cloud.snapshot()
        for target, key in [(actual["gke"], "createTime"), (actual["dataproc"], "clusterUuid"), (actual["sql"], "createTime"),
                            (actual["pool"], "instanceGroupUrls")]:
            original = target[key]
            target[key] = ["changed"] if isinstance(original, list) else "recreated"
            with self.assertRaises(LifecycleError):
                cloud.validate_snapshot(snapshot)
            target[key] = original

    def test_missing_kafka_policy_cannot_be_assumed_to_retain_events(self):
        cloud, _ = fixture()
        cloud.store.rows.pop("kafka_policy")
        with self.assertRaises(LifecycleError):
            cloud.snapshot()
    def test_mig_queries_never_follow_foreign_urls(self):
        cloud, _ = fixture()
        for url in ["https://evil.invalid/compute/v1/projects/assignment-test-123/zones/asia-south1-a/instanceGroups/group",
                    "https://www.googleapis.com/compute/v1/projects/other-project/zones/asia-south1-a/instanceGroups/group",
                    "http://www.googleapis.com/compute/v1/projects/assignment-test-123/zones/asia-south1-a/instanceGroups/group"]:
            with self.assertRaises(LifecycleError):
                cloud.group({"instanceGroupUrls": [url]})

    def test_auto_policy_drops_response_only_fields_and_does_not_repeat_noop(self):
        cloud, actual = fixture()
        cloud.request = Mock(return_value=actual["pool"])
        cloud.operation = Mock()
        cloud.autoscaling({"enabled": True, "minNodeCount": 2, "maxNodeCount": 2, "etag": "not-an-input"})
        cloud.operation.assert_not_called()
        cloud.request.reset_mock()
        cloud.request.side_effect = [actual["pool"], {"name": "operation-test"}]
        cloud.autoscaling({"enabled": False, "etag": "not-an-input"})
        self.assertEqual(cloud.request.call_args.args[2], {"autoscaling": {"enabled": False}})

    def test_read_only_probe_has_no_journal_writes(self):
        store = Store()
        cloud, _ = fixture()
        engine = Engine(CONFIG, store, cloud)
        cloud.pulse()
        self.assertEqual(store.rows, {})

    def test_lost_sql_stop_response_waits_for_the_pending_transition(self):
        cloud, _ = fixture()
        cloud.sleep = lambda _: None
        cloud.request = Mock(side_effect=[{"settings": {"activationPolicy": "NEVER"}},
            {"items": [{"status": "RUNNING"}]}, {"items": [{"status": "DONE"}]}])
        cloud.set_sql("NEVER")
        self.assertEqual(cloud.request.call_count, 3)
        self.assertTrue(all(call.args[0] == "GET" for call in cloud.request.call_args_list))

    def test_failed_cloud_response_does_not_echo_provider_contents(self):
        cloud, _ = fixture()
        cloud.session.request.return_value = SimpleNamespace(status_code=403, text="synthetic-private-marker")
        with self.assertRaises(LifecycleError) as error:
            cloud.request("GET", cloud.cluster)
        self.assertNotIn("synthetic-private-marker", str(error.exception))

    def test_real_yarn_lookup_matches_unique_application_name_before_stop(self):
        name = spec(ENV)[2]["reference"]["jobId"]
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps({"apps": {"app": [
            {"id": "application_456_0001", "name": "unrelated"},
            {"id": "application_123_0001", "name": name}]}}).encode()
        responses = iter([{"jobs": [{"jid": "a"*32, "state": "RUNNING"}]}, {"request-id": "b"*32},
                          {"status": {"id": "COMPLETED"}, "operation": {"location": locations(CONFIG)["savepoints"]+"pause/savepoint-safe"}}])
        with patch("deploy.flink_control.urlopen", return_value=response) as opened:
            result = stop({"job_name": name, "application_id": None, "target": locations(CONFIG)["savepoints"]+"pause"},
                          request=lambda *args: next(responses))
        self.assertIn("127.0.0.1:8088/ws/v1/cluster/apps", opened.call_args.args[0])
        self.assertEqual(result["application_id"], "application_123_0001")

class ReviewedPlans(unittest.TestCase):
    def environment(self, directory):
        root = Path(directory)
        for name in ["deploy/config.team.json", "deploy/profiles.json", "deploy/terraform/cloud/main.tf.json",
                     ".local-build/config/team/cloud.tfvars.json", ".local-build/config/team/cloud-backend.hcl",
                     "deploy/terraform/cloud/secrets.auto.tfvars.json"]:
            path = root/name;path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(CONFIG) if name.endswith("config.team.json") else "{}")
        return root

    def test_apply_uses_reviewed_file_without_running_a_second_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.environment(directory)
            calls = []
            def command(args, **kwargs):
                calls.append(list(args))
                for value in args:
                    if value.startswith("-out="):
                        Path(value.split("=", 1)[1]).write_bytes(b"synthetic-terraform-plan")
                return SimpleNamespace(stdout='{"resource_id":{"value":"synthetic"}}')
            with patch("deploy.cloud_stage.ROOT", root), patch("deploy.cloud_stage.guard_running"), \
                 patch("deploy.cloud_stage.resolve", side_effect=lambda args: args), \
                 patch("deploy.cloud_stage.subprocess.run", side_effect=command), patch("sys.stdout", new_callable=io.StringIO):
                cloud_stage.main(["cloud"])
                calls.clear()
                cloud_stage.main(["cloud", "--apply-reviewed"])
            self.assertFalse(any("plan" in call for call in calls))
            self.assertEqual(sum("apply" in call for call in calls), 1)
            self.assertTrue((root/".local-build/config/team/cloud-outputs.json").exists())

    def test_kafka_policy_receipt_is_written_only_after_successful_apply(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.environment(directory)
            folder = root/"deploy/terraform/kafka";folder.mkdir(parents=True)
            (folder/"main.tf.json").write_text("{}")
            (folder/"secrets.auto.tfvars.json").write_text('{"marker":"synthetic-private"}')
            (root/".local-build/config/team/kafka.tfvars.json").write_text('{"retention_days":21}')
            (root/".local-build/config/team/kafka-backend.hcl").write_text("")
            store = Store()
            def command(args, **kwargs):
                for value in args:
                    if value.startswith("-out="):
                        Path(value.split("=", 1)[1]).write_bytes(b"synthetic-reviewed-plan")
                return SimpleNamespace(stdout="{}")
            with patch("deploy.cloud_stage.ROOT", root), patch("deploy.cloud_stage.guard_running"), \
                 patch("deploy.cloud_stage.GCSStore", return_value=store), \
                 patch("deploy.cloud_stage.resolve", side_effect=lambda args: args), \
                 patch("deploy.cloud_stage.subprocess.run", side_effect=command), patch("sys.stdout", new_callable=io.StringIO):
                cloud_stage.main(["kafka"])
                self.assertNotIn("kafka_policy", store.rows)
                cloud_stage.main(["kafka", "--apply-reviewed"])
            self.assertEqual(store.rows["kafka_policy"]["retention_days"], 21)
            self.assertNotIn("synthetic-private", json.dumps(store.rows))

    def test_changed_input_or_plan_never_reaches_apply(self):
        for changed in ["plan", "private"]:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                root = self.environment(directory)
                calls = []
                def command(args, **kwargs):
                    calls.append(list(args))
                    for value in args:
                        if value.startswith("-out="):
                            Path(value.split("=", 1)[1]).write_bytes(b"synthetic-plan")
                    return SimpleNamespace(stdout="{}")
                with patch("deploy.cloud_stage.ROOT", root), patch("deploy.cloud_stage.guard_running"), \
                     patch("deploy.cloud_stage.resolve", side_effect=lambda args: args), \
                     patch("deploy.cloud_stage.subprocess.run", side_effect=command), patch("sys.stdout", new_callable=io.StringIO):
                    cloud_stage.main(["cloud"])
                    target = root/(".local-build/config/team/cloud.tfplan" if changed == "plan" else "deploy/terraform/cloud/secrets.auto.tfvars.json")
                    target.write_bytes(b"changed-synthetic-input")
                    calls.clear()
                    with self.assertRaises(SystemExit):
                        cloud_stage.main(["cloud", "--apply"])
                self.assertFalse(any("apply" in call for call in calls))

if __name__ == "__main__":
    unittest.main()
