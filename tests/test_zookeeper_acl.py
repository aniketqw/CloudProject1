import unittest
from task_scheduler.coordination import Coordination

ENV = {"APP_ENV": "local", "ZK_HOSTS": "127.0.0.1:2181"}


class ZookeeperAcl(unittest.TestCase):
    def test_credential_closes_new_nodes_to_everyone_else(self):
        client = Coordination(environ={**ENV, "ZK_AUTH": "food:s3cret"}).client
        acl = client.default_acl
        self.assertEqual(len(acl), 1)
        self.assertEqual(acl[0].id.scheme, "digest")
        self.assertTrue(acl[0].id.id.startswith("food:"))
        self.assertNotIn("s3cret", acl[0].id.id)  # stored hashed, never the plain password
        self.assertEqual(client.auth_data, {("digest", "food:s3cret")})

    def test_without_a_credential_behaviour_is_unchanged(self):
        client = Coordination(environ=ENV).client
        self.assertIsNone(client.default_acl)


if __name__ == "__main__":
    unittest.main()


class WorkerCache(unittest.TestCase):
    def _coordination(self):
        c = Coordination(environ=ENV)
        c.guard = lambda: None
        c.loads = 0
        def load():
            c.loads += 1
            return [{"worker_id": "w", "name": "n", "capabilities": ["payment"], "session": "1"}]
        c._load_workers = load
        return c

    def test_unchanged_worker_list_is_not_read_again(self):
        c = self._coordination()
        for _ in range(20):
            c.workers()
        self.assertEqual(c.loads, 1)

    def test_a_watch_event_forces_one_fresh_read(self):
        c = self._coordination()
        c.workers()
        c._workers_changed(["w", "x"])
        c.workers()
        c.workers()
        self.assertEqual(c.loads, 2)

    def test_callers_cannot_change_the_cache(self):
        c = self._coordination()
        c.workers()[0]["name"] = "changed"
        self.assertEqual(c.workers()[0]["name"], "n")
