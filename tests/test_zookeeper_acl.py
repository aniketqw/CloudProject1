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
