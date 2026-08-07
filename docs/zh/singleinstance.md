# wtfutil.singleinstance

通过 **非阻塞文件锁**（`portalocker`）保证同一台机器上同一脚本（或同一 `flavor_id`）只运行一个实例。默认锁文件在系统临时目录。

```python
from wtfutil.singleinstance import SingleInstance, SingleInstanceException, single_instance
```

## 符号

| 符号 | 说明 |
|------|------|
| `SingleInstanceException` | 已有实例占用锁时抛出 |
| `SingleInstance(flavor_id="", lockfile="")` | 上下文管理器 |
| `single_instance(flavor_id="", lockfile="")` | 装饰器工厂 |

## 参数

| 参数 | 说明 |
|------|------|
| `flavor_id` | 可选标识；同一脚本可用不同 `flavor_id` 区分多套单实例（如 `"worker"` / `"scheduler"`） |
| `lockfile` | 自定义锁文件路径；为空时自动生成：`{临时目录}/{脚本名}[-{flavor_id}].lock` |

默认锁名会根据 `sys.argv[0]` 的绝对路径生成，并替换 `/`、`\`、`:` 等非法字符。

## 示例

```python
# 上下文管理器
try:
    with SingleInstance(flavor_id="job"):
        run_main()
except SingleInstanceException as e:
    print(e)  # 已有实例正在运行

# 装饰器
@single_instance(flavor_id="job")
def main():
    run_main()

# 自定义锁路径
with SingleInstance(lockfile=r"D:\run\myapp.lock"):
    ...
```

## 说明

- `__enter__` 使用 `LOCK_EX | LOCK_NB`，若锁被占用立即抛 `SingleInstanceException`。
- `__exit__` 释放并关闭锁，但有意保留可复用的锁文件；解锁后再删除会在 Unix 上引入 inode/路径竞态。
- 获取锁失败时会先关闭刚打开的文件句柄，再抛出 `SingleInstanceException`。
- 实现参考 tendo 相关讨论，减轻 Windows 下多线程/子进程的锁竞争问题。
- 本地测试：`python -m wtfutil.singleinstance` 会进入循环直到 Ctrl+C；开第二个终端再运行可验证互斥。
