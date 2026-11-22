# B. Serverless, REST, gRPC and queues

## 1. The requirement
The services talk over REST, gRPC and message queues, plus a serverless function.

## 2. Original code
The design was in place. It had never been seen running on the cloud; five chart defects stopped it from starting.

## 3. Changes
ZooKeeper YAML quoting (T-049), DNS egress in the network policy, the Cloud SQL proxy address and the readiness probe (T-052 to T-054), ingress last and a free HTTPS name (T-055, T-059, T-060). All original-chart defects except the hostname.

## 4. See it working
Port-forward the customer, restaurant and order services; create a customer, address, restaurant and menu item; POST `/orders` (numeric customer and address ids). Pay with `POST /payments/orders/<id>` (needs `expected_version`, `scenario`, an Idempotency-Key of 8+ characters). Details in `docs/evidence/07-order-flow/ORDER-FLOW.md`.

## 5. Evidence
`docs/evidence/07-order-flow/`, `06-app-running/`.

## 6. Result
PASS for the order path, 2026-11-22: HTTP 201, gRPC to Restaurant, `OrderCreated` in Kafka, payment to PAID in about 9 s, a notification delivered through Pub/Sub and the Cloud Function with a receipt object. The site answers over HTTPS on an sslip.io name (certificate Active) and redirects HTTP. Not covered: kitchen and delivery stages.

## 7. Open
Kitchen and delivery stages; the web UI login flow.
