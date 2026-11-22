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
`docs/evidence/09-failover/`.

## 6. Result
PARTIAL, 2026-11-22. Leader changed (epoch 2 to 29) after its pod was deleted; ZooKeeper connected; a payment task ran through a lease. Not run: worker reclaim mid-task, quorum loss.

## 7. Open
Worker reclaim without duplication; quorum loss and recovery.
