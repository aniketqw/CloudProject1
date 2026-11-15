"""Optional bounded MySQL pools for the small cloud profile; local/SQLite defaults stay intact."""
import os

def engine_options(uri, current=None, environ=None):
    env = os.environ if environ is None else environ
    options = dict(current or {"pool_pre_ping": True, "hide_parameters": True})
    driver = getattr(uri, "drivername", str(uri).split(":", 1)[0])
    if str(driver).startswith("sqlite") or not any(k in env for k in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT")):
        return options
    limits = {"DB_POOL_SIZE": ("pool_size", 2, 1, 4),
              "DB_MAX_OVERFLOW": ("max_overflow", 0, 0, 2),
              "DB_POOL_TIMEOUT": ("pool_timeout", 10, 1, 30)}
    for key, (option, default, minimum, maximum) in limits.items():
        try:
            number = int(env.get(key, str(default)))
        except (ValueError, TypeError):
            raise ValueError("Invalid bounded database pool setting: " + key) from None
        if not minimum <= number <= maximum:
            raise ValueError("Database pool setting is outside the demo limits: " + key)
        options[option] = number
    options["pool_recycle"] = 300
    options["hide_parameters"] = True
    options["pool_pre_ping"] = True
    return options
