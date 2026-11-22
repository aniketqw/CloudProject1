"""TLS for the one gRPC path (Order to Restaurant). Certificates arrive as PEM text in environment variables, from a
Secret Manager secret (see deploy/terraform/cloud/grpc_tls.tf). Without them the code behaves as before (plain text),
which is what the local stacks use."""
import os
import grpc


def server_credentials(environ=None):
    env = os.environ if environ is None else environ
    cert, key = env.get("GRPC_TLS_CERT", ""), env.get("GRPC_TLS_KEY", "")
    if not (cert and key):
        return None
    return grpc.ssl_server_credentials([(key.encode(), cert.encode())])


def channel(target, environ=None):
    env = os.environ if environ is None else environ
    ca = env.get("GRPC_TLS_CA", "")
    if not ca:
        return grpc.insecure_channel(target)
    return grpc.secure_channel(target, grpc.ssl_channel_credentials(root_certificates=ca.encode()))
