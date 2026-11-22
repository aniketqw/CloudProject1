# F. Coordination (ZooKeeper)

## 1. The requirement
A scheduler elects a leader with ZooKeeper, workers hold leases, failure is handled safely.

## 2. Original code
Election, leases and fencing were implemented and unit tested; the ZooKeeper deployment itself did not start on the cloud.

## 3. Changes
ZooKeeper env quoting (T-049), DNS egress (T-052), readiness probe (T-054), pod disruption budget handling for pause (T-066).

## 4. See it working
Port-forward `task-api`, `curl localhost:8085/scheduler`, delete the leader pod, read it again.

## 5. Evidence
`docs/evidence/09-failover/` and the drill output in trace T-084.

## 6. Result
PASS, 2026-11-22 (access control added, watches not). Access control: scheduler and workers authenticate with a digest credential and every znode they create is closed to others; an unauthenticated read gets `Insufficient permission` while the scheduler works (`evidence/18-zookeeper-acl/`, T-088). Leader failover (epoch 2 to 29). Both payment workers were deleted two seconds after a payment started: the order still reached PAID with exactly one capture event (note: the payment is fast, so it may already have been claimed before the deletion; this shows no duplicate, not a reclaim mid-flight). Two of three ZooKeeper pods deleted: the scheduler endpoint was unavailable for a few seconds and returned with epoch 2; an order placed afterwards paid.

## 7. Open
ZooKeeper watches instead of 0.25 s polling (S4, optional); a drill that kills a worker while it provably holds a lease.
