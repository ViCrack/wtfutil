# wtfutil.configutil

Unified `wtfconfig.ini` loading with section merge and mtime-based hot reload.

```python
from wtfutil.configutil import ensure_section, get_wtfconfig_path, merge_section, reload_wtfconfig

defaults = {"BASE_URL": "https://party.mem.mk"}
cfg = {}
ensure_section(cfg, defaults, "memshell", uppercase_keys=True, env_map={"BASE_URL": "MEMSHELL_BASE_URL"})
```

## Lookup order

cwd → `resource/wtfconfig.ini` → `~/wtfconfig.ini`.

## Precedence

built-in defaults ← ini section ← environment variables (highest).

## Hot reload

- Whole-file cache keyed by `path + mtime`.
- `ensure_section` updates `target` on first load, path/mtime changes, section/default/environment-map changes, related environment-value changes, or `force_reload=True`.
- Unchanged signature leaves `target` alone (keeps runtime edits).
- Each target keeps only its latest application signature and object identity, preventing stale section matches and object-ID reuse; tracking is bounded to 256 recent targets.
- `reload_wtfconfig()` drops caches.

## API

| Symbol | Description |
|--------|-------------|
| `get_wtfconfig_path()` | Resolve ini path or `None` |
| `load_ini_file(force_reload=False)` | Cached `ConfigObj` |
| `merge_section(defaults, section, ...)` | New dict |
| `ensure_section(target, defaults, section, ...)` | Hot-apply into `target` |
| `reload_wtfconfig()` | Invalidate caches |

## Consumers

| Section | Module |
|---------|--------|
| `[notify]` | `notifyutil.push_config` |
| `[img]` | `imgutil.img_config` |
| `[memshell]` | `memshellutil.memshell_config` |
