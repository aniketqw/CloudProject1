import datetime
import unittest

import grpc

from common import grpc_tls

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
except ImportError:  # the certificates for this test need the cryptography package
    x509 = None


def pem_key(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()


def make_certificates():
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(1).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=1))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(ca_key, hashes.SHA256()))
    key = ec.generate_private_key(ec.SECP256R1())
    cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
            .issuer_name(ca_name).public_key(key.public_key()).serial_number(2).not_valid_before(now)
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    pem = lambda c: c.public_bytes(serialization.Encoding.PEM).decode()
    return {"GRPC_TLS_CA": pem(ca), "GRPC_TLS_CERT": pem(cert), "GRPC_TLS_KEY": pem_key(key)}


@unittest.skipIf(x509 is None, "cryptography is not installed")
class GrpcTls(unittest.TestCase):
    def test_server_and_client_speak_tls_and_plain_text_is_refused(self):
        from concurrent import futures
        env = make_certificates()
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        handler = grpc.method_handlers_generic_handler("t.Echo", {"Say": grpc.unary_unary_rpc_method_handler(
            lambda request, context: request)})
        server.add_generic_rpc_handlers((handler,))
        port = server.add_secure_port("localhost:0", grpc_tls.server_credentials(env))
        server.start()
        try:
            with grpc_tls.channel(f"localhost:{port}", env) as secure:
                self.assertEqual(secure.unary_unary("/t.Echo/Say")(b"hi", timeout=5), b"hi")
            with grpc_tls.channel(f"localhost:{port}", {}) as plain:  # no CA: plain-text client
                with self.assertRaises(grpc.RpcError):
                    plain.unary_unary("/t.Echo/Say")(b"hi", timeout=3)
        finally:
            server.stop(0)

    def test_without_certificates_nothing_changes(self):
        self.assertIsNone(grpc_tls.server_credentials({}))


if __name__ == "__main__":
    unittest.main()
