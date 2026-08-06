# wtfutil.memshellutil

MemShellParty HTTP client for generating Java memory shells. Default host: [https://party.mem.mk](https://party.mem.mk). CLI: **`memshell`** (not in `__all__`).

Upstream: [MemShellParty](https://github.com/ReaJason/MemShellParty) · [Issue #143](https://github.com/ReaJason/MemShellParty/issues/143)

**No built-in cache**; cache identical configs yourself if needed.

```python
from wtfutil import MemShellParty

with MemShellParty() as client:
    result = client.generate(
        shell_type="Listener",
        target_jre_version=53,
        behinder_pass="pass",
        header_value="secret",
    )
    print(result["packResult"])
```

## Configuration

Precedence: constructor `base_url=` > env `MEMSHELL_BASE_URL` > `wtfconfig.ini` `[memshell] BASE_URL` > default `https://party.mem.mk`.

## MemShellParty

| Method | Description |
|--------|-------------|
| `get_config()` | `GET /api/config` |
| `get_packers_tree()` | `GET /api/config/packers/tree` |
| `get_command_configs()` | `GET /api/config/command/configs` |
| `generate(body=None, **)` | `POST /api/memshell/generate` |

Defaults: `Tomcat` / **Behinder** / `Listener` / JRE `50` / `shrink=True` / `staticInitialize=True` / `packer=DefaultBase64`. Auto `byPassJavaModule=True` when JRE >= 53. Command defaults: `RAW` / `RuntimeExec`.

## Parameter reference (official fields)

| CLI / kwargs | Official field | Meaning |
|--------------|----------------|---------|
| `--server` | shellConfig.server | Target middleware/framework |
| `--server-version` | shellConfig.serverVersion | Server version (rarely needed) |
| `--shell-tool` | shellConfig.shellTool | Tool: Behinder / Godzilla / Command / … |
| `--shell-type` | shellConfig.shellType | Mount type: Listener / Filter / Valve / … |
| `--target-jre-version` | shellConfig.targetJreVersion | Class file major version (50=Java6 … 65=21) |
| `--debug` | shellConfig.debug | Print inject/debug stack traces |
| `--by-pass-java-module` | shellConfig.byPassJavaModule | Bypass JDK9+ modules via Unsafe defineClass |
| `--no-shrink` | shellConfig.shrink=false | Default on: ASM SKIP_DEBUG shrink |
| `--probe` | shellConfig.probe | Wrap injector in probe shell for remote verify |
| `--lambda-suffix` | shellConfig.lambdaSuffix | Append `$Proxy0$$Lambda$1` to class names |
| `--url-pattern` | injectorConfig.urlPattern | Mount URL (default `/*`) |
| `--injector-class-name` | injectorConfig.injectorClassName | Injector FQCN (empty=random) |
| `--no-static-initialize` | staticInitialize=false | Default on: static block calls ctor |
| `--shell-class-name` | shellClassName | Shell FQCN (empty=random) |
| `--behinder-pass` | behinderPass | Behinder password (empty=random) |
| `--godzilla-pass` / `--godzilla-key` | godzillaPass / godzillaKey | Godzilla pass/key |
| `--ant-sword-pass` | antSwordPass | AntSword password |
| `--password` / `password` | (mapped by shellTool) | Convenience password → Behinder/Godzilla/AntSword *Pass; specific `--*-pass` wins |
| `--key` / `key` | godzillaKey | Convenience Godzilla key; `--godzilla-key` wins |
| `--header-name` / `--header-value` | headerName / headerValue | Entry header gate |
| `--command-param-name` | commandParamName | Command param/header name |
| `--command-template` | commandTemplate | Template with `{command}` |
| `--encryptor` | encryptor | RAW / BASE64 / DOUBLE_BASE64 |
| `--implementation-class` | implementationClass | RuntimeExec / ForkAndExec |
| `--shell-class-base64` | shellClassBase64 | Custom shell .class Base64 |
| `--packer` | packer | Packing format |

See also `memshell generate --help`.

## CLI

```bash
memshell generate --help
memshell generate -o payload.txt
memshell install-skill --project
```

## JRE class version

| Java | targetJreVersion |
|------|------------------|
| 6 | 50 |
| 8 | 52 |
| 9 | 53 |
| 11 | 55 |
| 17 | 61 |
| 21 | 65 |

## Helpers

- `build_generate_body(...)` / `extract_generate_meta(...)` / `MemShellPartyError`
