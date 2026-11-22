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
PASS, 2026-11-22. Leader failover (epoch 2 to 29). Both payment workers were deleted two seconds after a payment started: the order still reached PAID with exactly one capture event (note: the payment is fast, so it may already have been claimed before the deletion; this shows no duplicate, not a reclaim mid-flight). Two of three ZooKeeper pods deleted: the scheduler endpoint was unavailable for a few seconds and returned with epoch 2; an order placed afterwards paid.

## 7. Open
A drill that kills a worker while it provably holds a lease (a slower payment scenario).
