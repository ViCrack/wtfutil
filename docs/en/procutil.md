# wtfutil.procutil (Windows only)

Process find/suspend/resume; Python processes by script path or command line.

```python
from wtfutil import find_process_by_name, suspend_process
```

| Symbol | Description |
|--------|-------------|
| `find_process_by_name(name)` | PIDs by process name |
| `suspend_process(name)` / `suspend_process_by_pid(pid)` | Suspend threads |
| `resume_process(name)` / `resume_process_by_pid(pid)` | Resume threads |
| `find_python_process_by_script(script)` | First matching Python process |
| `find_python_processes_by_script(script)` | All matches |
| `find_python_process_details_by_script(script)` | Detailed list |
| `kill_python_processes_by_script(script)` | Kill matches |
| `find_python_processes_by_cmdline(pattern)` | Match command line |
| `find_python_process_details_by_cmdline(pattern)` | Details |
| `kill_python_processes_by_cmdline(pattern)` | Kill matches |
| `list_all_python_process_details()` | All Python processes |
