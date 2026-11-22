# G. Data stores

## 1. The requirement
SQL, a document database and object storage are all used.

## 2. Original code
Cloud SQL, Firestore and Cloud Storage were declared.

## 3. Changes
Firestore seed in Terraform (T-015), Firestore delete switch (T-044), index import after an interrupted apply (T-063).

## 4. See it working
Order rows in SQL via `GET /orders/<id>`; restaurant in Firestore via the restaurant API; receipt object in the receipts bucket.

## 5. Evidence
`docs/evidence/07-order-flow/`. An order survived a Cloud SQL stop and start (`paused` test, T-061).

## 6. Result
PASS, 2026-11-22: order in SQL, restaurant in Firestore, receipt object written to Cloud Storage, and analytics results in a Firestore collection (`16-flink-results/`).

## 7. Open
None.
