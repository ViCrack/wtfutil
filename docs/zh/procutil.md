# wtfutil.procutil（仅 Windows）

进程查找、挂起/恢复、按脚本或命令行匹配 Python 进程。

```python
from wtfutil import find_process_by_name, suspend_process
```

## 符号索引

| 符号 | 说明 |
|------|------|
| `find_process_by_name(name)` | 按进程名返回 PID 列表 |
| `suspend_process(name)` / `suspend_process_by_pid(pid)` | 挂起线程 |
| `resume_process(name)` / `resume_process_by_pid(pid)` | 恢复线程 |
| `find_python_process_by_script(script)` | 首个匹配脚本路径的 Python 进程 |
| `find_python_processes_by_script(script)` | 全部匹配 |
| `find_python_process_details_by_script(script)` | 详细信息列表 |
| `kill_python_processes_by_script(script)` | 结束匹配进程 |
| `find_python_processes_by_cmdline(pattern)` | 按命令行匹配 |
| `find_python_process_details_by_cmdline(pattern)` | 详细信息 |
| `kill_python_processes_by_cmdline(pattern)` | 结束匹配 |
| `list_all_python_process_details()` | 列出所有 Python 进程详情 |
