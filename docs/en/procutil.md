# wtfutil.procutil

Find/kill processes (cross-platform via `psutil`); suspend/resume threads (**Windows only** — raises `OSError` elsewhere).

Empty or whitespace-only names/patterns raise `ValueError` instead of matching every Python process. Destructive helpers skip the current process; suspending the current PID is rejected. `python -m` and `python -c` commands are not treated as script-file processes.

Import process APIs directly from their owning public submodule:

```python
from wtfutil.procutil import find_process_by_name, resume_process, suspend_process
```

## Examples

```python
from wtfutil.procutil import (
    find_python_processes_by_script,
    kill_python_processes_by_script,
    kill_python_processes_by_cmdline,
    list_all_python_process_details,
    resume_process,
    suspend_process,
)

# Find / kill by script path (Linux / macOS / Windows)
find_python_processes_by_script("worker.py")
kill_python_processes_by_script("worker.py")
kill_python_processes_by_cmdline("celery worker")

# Suspend / resume (Windows only)
suspend_process("notepad.exe")
resume_process("notepad.exe")

for p in list_all_python_process_details():
    print(p["pid"], p.get("script"), p.get("cmdline"))
```

CLI: **[pykill](pykill.md)** — `pykill`, `pykill worker.py -l`.

## API index

| Symbol | Description |
|--------|-------------|
| `find_process_by_name(name)` | PID by name (`None` if missing) |
| `find_python_process_by_script(script_name)` | First matching Python process PID, or `None` |
| `find_python_processes_by_script(script_name)` | All matching Python process PIDs |
| `find_python_process_details_by_script(script_name)` | Matching process detail dictionaries |
| `kill_python_processes_by_script(script_name)` | Kill all script-path matches |
| `find_python_processes_by_cmdline(pattern)` | PIDs whose command line contains `pattern` |
| `find_python_process_details_by_cmdline(pattern)` | Matching command-line detail dictionaries |
| `kill_python_processes_by_cmdline(pattern)` | Kill all command-line matches |
| `list_all_python_process_details()` | All Python processes |
| `suspend_process(process_name)` | Suspend a named process (Windows only) |
| `suspend_process_by_pid(pid)` | Suspend a PID (Windows only) |
| `resume_process(process_name)` | Resume a named process (Windows only) |
| `resume_process_by_pid(pid)` | Resume a PID (Windows only) |
