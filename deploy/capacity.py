"""Shared, non-secret capacity policies. Demo is the default; never escalates automatically."""
import copy
import json
from pathlib import Path

PROFILES = json.loads((Path(__file__).with_name("profiles.json")).read_text(encoding="utf-8"))

def selected(config):
    name = config.get("compute_profile", "demo")
    if name not in PROFILES:
        raise ValueError("compute_profile must be demo or standard.")
    return name, copy.deepcopy(PROFILES[name])

def apply_to_values(config, values):
    name, capacity = selected(config)
    values["computeProfile"] = name
    values["env"]["KAFKA_RETENTION_DAYS"] = str(capacity["kafka_retention_days"])
    values["resources"] = capacity["resources"]
    values["sqlProxyResources"] = capacity["sql_proxy_resources"]
    # Preserve two schedulers and workers, the three ZooKeeper members and both HPAs.
    # Keep short-lived analytics and initialization jobs unchanged.
    if name == "demo":
        values["env"].update(DB_POOL_SIZE="2", DB_MAX_OVERFLOW="0", DB_POOL_TIMEOUT="10")
        for workload in values["workloads"].values():
            if not workload.get("factory") and not workload.get("port"):
                workload["resources"] = {"requests": {"cpu": "25m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "512Mi"}}
        values["hpa"]["max"] = 4
        values["workloads"]["customer-service"]["resources"] = {
            "requests": {"cpu": "50m", "memory": "128Mi"},
            "limits": {"cpu": "1000m", "memory": "512Mi"}}
        values["workloads"]["order-service"]["resources"] = copy.deepcopy(
            values["workloads"]["customer-service"]["resources"])
        values["workloads"]["kitchen-sync"]["resources"] = {
            "requests": {"cpu": "50m", "memory": "192Mi"},
            "limits": {"cpu": "500m", "memory": "512Mi"}}
    return capacity
