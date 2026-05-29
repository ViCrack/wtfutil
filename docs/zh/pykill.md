# pykill（命令行工具）

根据脚本路径或命令行模式列出/终止 Python 进程的交互式 CLI。`pip install wtfutil` 后可用命令 **`pykill`**。未纳入 `wtfutil.__all__`；实现见 `wtfutil/pykill.py`。

底层调用 `wtfutil.procutil`，展示使用 `rich` 表格，无参数时通过 `questionary` 多选要结束的进程。

## 用法

```text
pykill                                # 列出所有 Python 进程，交互多选后 kill
pykill myscript.py                    # 按脚本路径匹配并终止
pykill myscript.py -l                 # 仅列出匹配进程，不终止
pykill -c "worker --queue"            # 按命令行子串匹配
pykill -l                             # 仅列出所有 Python 进程
```

| 参数 | 说明 |
|------|------|
| `PATTERN`（可选） | 脚本路径或命令行匹配串；省略则针对全部 Python 进程 |
| `-c`, `--cmdline` | 按完整命令行匹配，而非脚本路径 |
| `-l`, `--list` | 只列出，不执行 kill |

## 行为说明

- **无 `PATTERN`**：用 Rich 打印进程表（不含当前 `pykill` 自身），随后可多选 PID 批量终止；加 `-l` 则只列出不杀。
- **有 `PATTERN`**：调用 `find_python_process_details_by_script` 或 `find_python_process_details_by_cmdline`，打印表后默认终止全部匹配项；`-l` 仅列出。
- 表格列：PID、进程名、脚本、绝对路径、工作目录、完整命令行。
- 终止使用 `psutil.Process(pid).kill()`，并提示成功、进程已退出或权限不足。

## 在代码中调用

```python
from wtfutil.pykill import main

raise SystemExit(main())
```

脚本内批量杀进程更推荐直接用 [procutil](procutil.md)：`kill_python_processes_by_script`、`kill_python_processes_by_cmdline` 等。
