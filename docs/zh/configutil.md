# wtfutil.configutil

统一读取 `wtfconfig.ini`，支持按段合并与文件 mtime 热加载。

```python
from wtfutil import ensure_section, merge_section, reload_wtfconfig, get_wtfconfig_path

defaults = {"BASE_URL": "https://party.mem.mk"}
cfg = {}
ensure_section(cfg, defaults, "memshell", uppercase_keys=True, env_map={"BASE_URL": "MEMSHELL_BASE_URL"})
```

## 查找路径

与历史一致：当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。

## 优先级

内置 defaults ← ini 对应段 ← 环境变量（最高）。

## 热加载

- 整文件按 `path + mtime` 缓存。
- `ensure_section`：仅**首次**或 **mtime/路径变化**（或 `force_reload=True`）时 `target.clear(); update(merged)`，返回 `True`。
- 签名未变时不改 `target`，保留运行时手动改写。
- `reload_wtfconfig()`：丢弃缓存，下次必重读。

## API

| 符号 | 说明 |
|------|------|
| `get_wtfconfig_path()` | 解析 ini 路径，可能为 `None` |
| `load_ini_file(force_reload=False)` | 带缓存的 `ConfigObj`，无文件返回 `None` |
| `merge_section(defaults, section, ...)` | 返回新 dict，不改调用方 |
| `ensure_section(target, defaults, section, ...)` | 热更新写入 `target`，返回是否刷新 |
| `reload_wtfconfig()` | 强制失效缓存 |

`merge_section` / `ensure_section` 常用参数：

- `uppercase_keys`：ini 键转大写（`[img]` / `[memshell]`）
- `env_map`：config 键 → 环境变量名（如 `BASE_URL` → `MEMSHELL_BASE_URL`）

## 已接入模块

| 段 | 模块 |
|----|------|
| `[notify]` | `notifyutil.push_config`（`send` 前 ensure，刷新时重建通道列表） |
| `[img]` | `imgutil.img_config` |
| `[memshell]` | `memshellutil.memshell_config` |
