import unittest
from common.kafka import kafka_config


class KafkaConfigurationTests(unittest.TestCase):
    def test_cloud_defaults_require_credentials(self):
        with self.assertRaisesRegex(ValueError, "SASL_SSL requires"):
            kafka_config("test", {"KAFKA_BOOTSTRAP_SERVERS": "broker.example:9092"})

    def test_cloud_defaults_keep_tls_and_sasl(self):
        config = kafka_config("test", {
            "KAFKA_BOOTSTRAP_SERVERS": "broker.example:9092",
            "KAFKA_API_KEY": "dummy-key", "KAFKA_API_SECRET": "dummy-secret",
        })
        self.assertEqual(config["security.protocol"], "SASL_SSL")
        self.assertEqual(config["sasl.mechanisms"], "PLAIN")
        self.assertEqual(config["sasl.username"], "dummy-key")

    def test_local_plaintext_needs_no_cloud_credentials(self):
        config = kafka_config("test", {"APP_ENV": "local", "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT",
                                       "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092"})
        self.assertEqual(config["security.protocol"], "PLAINTEXT")
        self.assertFalse(any(key.startswith("sasl.") for key in config))

    def test_plaintext_is_rejected_without_local_opt_in(self):
        for app_env in [None, "production", "staging"]:
            env = {"KAFKA_BOOTSTRAP_SERVERS": "kafka:9092", "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT"}
            if app_env is not None:
                env["APP_ENV"] = app_env
            with self.subTest(app_env=app_env), self.assertRaisesRegex(ValueError, "APP_ENV=local"):
                kafka_config("test", env)

    def test_local_mode_does_not_forward_cloud_secrets(self):
        config = kafka_config("test", {"APP_ENV": "local", "KAFKA_SECURITY_PROTOCOL": "PLAINTEXT",
            "KAFKA_BOOTSTRAP_SERVERS": "kafka:9092", "KAFKA_API_KEY": "unused-key",
            "KAFKA_API_SECRET": "unused-secret"})
        self.assertNotIn("sasl.password", config)
        self.assertNotIn("sasl.username", config)

    def test_missing_broker_and_unsupported_protocol_fail_clearly(self):
        with self.assertRaisesRegex(ValueError, "KAFKA_BOOTSTRAP_SERVERS"):
            kafka_config("test", {})
        with self.assertRaisesRegex(ValueError, "must be SASL_SSL or PLAINTEXT"):
            kafka_config("test", {"KAFKA_BOOTSTRAP_SERVERS": "broker:9092", "KAFKA_SECURITY_PROTOCOL": "SSL"})


if __name__ == "__main__":
    unittest.main()


class BrokerCertificateAuthority(unittest.TestCase):
    ENV = {"KAFKA_BOOTSTRAP_SERVERS": "10.40.0.9:9092", "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
           "KAFKA_API_KEY": "food", "KAFKA_API_SECRET": "secret"}

    def test_ca_is_passed_to_the_client_when_present(self):
        config = kafka_config("t", {**self.ENV, "KAFKA_SSL_CA": "-----BEGIN CERTIFICATE-----\nabc\n-----END CERTIFICATE-----\n"})
        self.assertIn("BEGIN CERTIFICATE", config["ssl.ca.pem"])

    def test_without_a_ca_the_default_trust_store_is_used(self):
        self.assertNotIn("ssl.ca.pem", kafka_config("t", self.ENV))
