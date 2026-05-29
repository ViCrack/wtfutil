# wtfutil.singleinstance

Single-instance lock via file lock + portalocker.

```python
from wtfutil import single_instance, SingleInstanceException
```

| Symbol | Description |
|--------|-------------|
| `SingleInstanceException` | Raised when another instance holds the lock |
| `SingleInstance` | Context manager: `with SingleInstance(flavor_id=..., lockfile=...):` |
| `single_instance` | Decorator factory: `@single_instance(flavor_id="...")` |

Lock file in OS temp dir, derived from script path + `flavor_id`.

```python
try:
    with single_instance(flavor_id="my_job"):
        run_job()
except SingleInstanceException:
    print("Already running")

@single_instance(flavor_id="my_job")
def main():
    run_job()
```
