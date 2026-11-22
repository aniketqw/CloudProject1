# TLS for the one gRPC path (Order to Restaurant). A private CA signs a server certificate for the Restaurant service; the
# three PEM texts are kept in Secret Manager and reach the pods as environment variables through External Secrets.
# Terraform state holds the private keys (the state bucket is private and versioned; see S8 in the gaps document).
resource "tls_private_key" "grpc_ca" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_self_signed_cert" "grpc_ca" {
  private_key_pem       = tls_private_key.grpc_ca.private_key_pem
  is_ca_certificate     = true
  validity_period_hours = 24 * 365
  allowed_uses          = ["cert_signing", "crl_signing"]

  subject {
    common_name = "${var.prefix}-internal-ca"
  }
}

resource "tls_private_key" "grpc_server" {
  algorithm   = "ECDSA"
  ecdsa_curve = "P256"
}

resource "tls_cert_request" "grpc_server" {
  private_key_pem = tls_private_key.grpc_server.private_key_pem
  dns_names       = ["restaurant-service", "restaurant-service.food.svc", "restaurant-service.food.svc.cluster.local", "localhost"]
  ip_addresses    = ["127.0.0.1"] # the pod's own health probe connects over the loopback address

  subject {
    common_name = "restaurant-service"
  }
}

resource "tls_locally_signed_cert" "grpc_server" {
  cert_request_pem      = tls_cert_request.grpc_server.cert_request_pem
  ca_private_key_pem    = tls_private_key.grpc_ca.private_key_pem
  ca_cert_pem           = tls_self_signed_cert.grpc_ca.cert_pem
  validity_period_hours = 24 * 365
  allowed_uses          = ["digital_signature", "server_auth"]
}
