# pykill (CLI)

Interactive CLI to list and kill Python processes. Installed as a **console script** (`pip install wtfutil` → `pykill` on PATH). Not exported in `wtfutil.__all__`; implementation: `wtfutil/pykill.py`.

Built on `wtfutil.procutil` (Windows-oriented process APIs) plus `psutil`, `rich`, and `questionary`.

## Usage

```text
pykill                                # list all Python processes, interactive multi-select kill
pykill myscript.py                    # match by script path, kill all matches
pykill myscript.py -l                 # list matches only, do not kill
pykill -c "worker --queue"            # match by command-line substring
pykill -l                             # list all Python processes only
```

| Argument | Description |
|----------|-------------|
| `PATTERN` (optional) | Script path or cmdline substring; omitted → all Python processes |
| `-c`, `--cmdline` | Match `PATTERN` against full command line instead of script path |
| `-l`, `--list` | List only; do not kill |

## Behavior

- **No `PATTERN`**: prints a Rich table of all Python processes (excluding self), then optional checkbox UI to select PIDs to kill.
- **With `PATTERN`**: finds matches via `find_python_process_details_by_script` or `find_python_process_details_by_cmdline`, prints table, then kills all matches unless `-l`.
- Table columns: PID, process name, script, absolute path, cwd, full cmdline.
- Kill uses `psutil.Process(pid).kill()`; reports success, already exited, or access denied.

## Programmatic use

```python
from wtfutil.pykill import main

raise SystemExit(main())
```

Prefer `procutil` APIs when embedding in your own scripts: `kill_python_processes_by_script`, `kill_python_processes_by_cmdline`, etc. See [procutil.md](procutil.md).
