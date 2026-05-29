# wtfutil.singleinstance

Prevent more than one instance of a script on the same machine using a **non-blocking file lock** (`portalocker`). Lock file defaults to the OS temp directory.

```python
from wtfutil import single_instance, SingleInstance, SingleInstanceException
```

## Symbols

| Symbol | Description |
|--------|-------------|
| `SingleInstanceException` | Raised when another instance already holds the lock |
| `SingleInstance(flavor_id="", lockfile="")` | Context manager |
| `single_instance(flavor_id="", lockfile="")` | Decorator factory |

## Parameters

| Parameter | Description |
|-----------|-------------|
| `flavor_id` | Optional suffix so the same script can run multiple single-instance “flavors” (e.g. `"worker"` vs `"scheduler"`) |
| `lockfile` | Custom lock path; if empty, auto: `{tempdir}/{script_basename}[-{flavor_id}].lock` |

Illegal path characters in the script path are normalized when building the default lock name.

## Examples

```python
# Context manager
try:
    with SingleInstance(flavor_id="my_job"):
        run_job()
except SingleInstanceException:
    print("Already running")

# Decorator
@single_instance(flavor_id="my_job")
def main():
    run_job()

# Custom lock file
with SingleInstance(lockfile="/var/run/myapp.lock"):
    ...
```

## Notes

- Lock is acquired on `__enter__` with `LOCK_EX | LOCK_NB` (fail fast if busy).
- On exit, unlocks and attempts to remove the lock file.
- Design avoids some Windows multi-thread lock races (see module docstring / tendo discussion).
- Test locally: `python -m wtfutil.singleinstance` runs a minimal loop until Ctrl+C.
