# wtfutil.procutil (Windows only)

Process find/suspend/resume; Python processes by script path or command line.

```python
from wtfutil import find_process_by_name, suspend_process
```

## Examples

```python
from wtfutil import (
    find_python_processes_by_script,
    kill_python_processes_by_script,
    kill_python_processes_by_cmdline,
    list_all_python_process_details,
)

find_python_processes_by_script("worker.py")
kill_python_processes_by_script("worker.py")
kill_python_processes_by_cmdline("celery worker")

suspend_process("notepad.exe")
resume_process("notepad.exe")

for p in list_all_python_process_details():
    print(p["pid"], p.get("script"), p.get("cmdline"))
```

CLI: **[pykill](pykill.md)** — `pykill`, `pykill worker.py -l`.

## API index

| Symbol | Description |
|--------|-------------|
| `find_process_by_name(name)` | PIDs by name |
| `suspend_process` / `suspend_process_by_pid` | Suspend |
| `resume_process` / `resume_process_by_pid` | Resume |
| `find_python_process_*_by_script` | Match script path |
| `kill_python_processes_by_script` | Kill matches |
| `find_python_processes_by_cmdline` / `kill_python_processes_by_cmdline` | Match cmdline |
| `list_all_python_process_details()` | All Python processes |
