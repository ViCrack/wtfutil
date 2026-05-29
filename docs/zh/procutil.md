# wtfutil.procutil（仅 Windows）

进程查找、挂起/恢复、按脚本或命令行匹配 Python 进程。

```python
from wtfutil import find_process_by_name, suspend_process
```

## 示例

```python
from wtfutil import (
    find_python_processes_by_script,
    kill_python_processes_by_script,
    suspend_process,
    resume_process,
)

# 按脚本路径查找 / 结束
procs = find_python_processes_by_script("worker.py")
kill_python_processes_by_script("worker.py")

# 按命令行子串
from wtfutil import kill_python_processes_by_cmdline
kill_python_processes_by_cmdline("celery worker")

# 挂起 / 恢复记事本（示例）
suspend_process("notepad.exe")
resume_process("notepad.exe")

# 列出所有 Python 进程详情
from wtfutil import list_all_python_process_details
for p in list_all_python_process_details():
    print(p["pid"], p.get("script"), p.get("cmdline"))
```

命令行工具见 **[pykill](pykill.md)**：`pykill`、`pykill worker.py -l`。

## API 索引

| 符号 | 说明 |
|------|------|
| `find_process_by_name(name)` | 按进程名返回 PID 列表 |
| `suspend_process` / `suspend_process_by_pid` | 挂起 |
| `resume_process` / `resume_process_by_pid` | 恢复 |
| `find_python_process_by_script` / `find_python_processes_by_script` | 按脚本路径 |
| `find_python_process_details_by_script` | 详细信息 |
| `kill_python_processes_by_script` | 结束匹配进程 |
| `find_python_processes_by_cmdline` / `kill_python_processes_by_cmdline` | 按命令行 |
| `list_all_python_process_details()` | 全部 Python 进程 |
