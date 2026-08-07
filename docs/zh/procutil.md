# wtfutil.procutil

进程查找与结束（跨平台，基于 `psutil`）；挂起 / 恢复线程（**仅 Windows**，非 Windows 抛 `OSError`）。

进程名、脚本名和命令行匹配串不能为空或纯空白，否则抛 `ValueError`，避免空串匹配全部 Python 进程。结束进程的 API 默认跳过当前进程；挂起当前 PID 会被拒绝。`python -m` / `python -c` 启动方式不作为脚本文件匹配。

推荐直接从公开子模块导入所需符号。也可使用 Python 的常规子模块导入写法 `from wtfutil import procutil`，再通过 `procutil.<符号>` 调用。

```python
from wtfutil.procutil import find_process_by_name, suspend_process
```

## 示例

```python
from wtfutil.procutil import (
    find_python_processes_by_script,
    kill_python_processes_by_script,
    kill_python_processes_by_cmdline,
    list_all_python_process_details,
    suspend_process,
    resume_process,
)

# 按脚本路径查找 / 结束（Linux / macOS / Windows）
procs = find_python_processes_by_script("worker.py")
kill_python_processes_by_script("worker.py")

# 按命令行子串
kill_python_processes_by_cmdline("celery worker")

# 挂起 / 恢复（仅 Windows）
suspend_process("notepad.exe")
resume_process("notepad.exe")

# 列出所有 Python 进程详情
for p in list_all_python_process_details():
    print(p["pid"], p.get("script"), p.get("cmdline"))
```

命令行工具见 **[pykill](pykill.md)**：`pykill`、`pykill worker.py -l`。

## API 索引

| 符号 | 说明 |
|------|------|
| `find_process_by_name(name)` | 按进程名返回 PID（未找到为 `None`） |
| `suspend_process` / `suspend_process_by_pid` | 挂起（仅 Windows） |
| `resume_process` / `resume_process_by_pid` | 恢复（仅 Windows） |
| `find_python_process_by_script(script_name)` | 按脚本路径返回第一个 PID（未找到为 `None`） |
| `find_python_processes_by_script(script_name)` | 按脚本路径返回所有 PID；带目录的路径只做精确匹配，纯文件名才回退文件名 |
| `find_python_process_details_by_script(script_name)` | 按脚本路径返回进程详情列表 |
| `kill_python_processes_by_script(script_name)` | 结束按脚本路径匹配的全部进程 |
| `find_python_processes_by_cmdline(pattern)` | 按命令行大小写不敏感子串返回 PID 列表 |
| `find_python_process_details_by_cmdline(pattern)` | 按命令行子串返回进程详情列表 |
| `kill_python_processes_by_cmdline(pattern)` | 结束按命令行子串匹配的全部进程 |
| `list_all_python_process_details()` | 返回全部 Python 进程详情 |

详情字典包含 `pid`、`name`、`script`、`script_abs`、`cwd`、`cmdline`。
