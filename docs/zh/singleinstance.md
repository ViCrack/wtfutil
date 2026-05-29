# wtfutil.singleinstance

单实例锁（文件锁 + portalocker）。

```python
from wtfutil import single_instance, SingleInstanceException
```

## 符号

| 符号 | 说明 |
|------|------|
| `SingleInstanceException` | 已有实例时抛出 |
| `SingleInstance` | 上下文管理器：`with SingleInstance(flavor_id=..., lockfile=...):` |
| `single_instance` | 装饰器：`@single_instance(flavor_id="...")` |

锁文件默认在系统临时目录，由脚本路径 + `flavor_id` 派生。

```python
try:
    with single_instance(flavor_id="job"):
        ...
except SingleInstanceException:
    print("已有实例在运行")
```
