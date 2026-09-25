# wtfutil API 文档索引

完整 API 按子模块拆分，便于查阅与 AI 索引。根目录 [README.md](../README.md) / [README_zh.md](../README_zh.md) 提供安装、快速入门、常用示例和模块总览。

> **1.3.0 迁移提示 / Migration note:** 包根级符号导入已移除；请从实际所属的 `wtfutil.<module>` 导入函数、类、常量和配置对象。例如使用 `from wtfutil.fileutil import read_lines`，而不是从 `wtfutil` 包根导入 `read_lines`。Package-root symbol imports were removed; import SDK symbols from their owning public submodules.

| 模块 | 英文 | 中文 |
|------|------|------|
| `wtfutil.util` | [en/util.md](en/util.md) | [zh/util.md](zh/util.md) |
| `wtfutil.httputil` | [en/httputil.md](en/httputil.md) | [zh/httputil.md](zh/httputil.md) |
| `wtfutil.fileutil` | [en/fileutil.md](en/fileutil.md) | [zh/fileutil.md](zh/fileutil.md) |
| `wtfutil.strutil` | [en/strutil.md](en/strutil.md) | [zh/strutil.md](zh/strutil.md) |
| `wtfutil.sqlutil` | [en/sqlutil.md](en/sqlutil.md) | [zh/sqlutil.md](zh/sqlutil.md) |
| `wtfutil.procutil` | [en/procutil.md](en/procutil.md) | [zh/procutil.md](zh/procutil.md) |
| `wtfutil.configutil` | [en/configutil.md](en/configutil.md) | [zh/configutil.md](zh/configutil.md) |
| `wtfutil.notifyutil` | [en/notifyutil.md](en/notifyutil.md) | [zh/notifyutil.md](zh/notifyutil.md) |
| `wtfutil.translateutil` | [en/translateutil.md](en/translateutil.md) | [zh/translateutil.md](zh/translateutil.md) |
| `wtfutil.memshellutil` | [en/memshellutil.md](en/memshellutil.md) | [zh/memshellutil.md](zh/memshellutil.md) |
| `wtfutil.daydaymaputil` / **`daydaymap`（CLI：管道、图标/证书）** | [en/daydaymaputil.md](en/daydaymaputil.md) | [zh/daydaymaputil.md](zh/daydaymaputil.md) |
| `wtfutil.imgutil` | [en/imgutil.md](en/imgutil.md) | [zh/imgutil.md](zh/imgutil.md) |
| `wtfutil.singleinstance` | [en/singleinstance.md](en/singleinstance.md) | [zh/singleinstance.md](zh/singleinstance.md) |
| **`pykill`（CLI）** | [en/pykill.md](en/pykill.md) | [zh/pykill.md](zh/pykill.md) |
| **`memshell`（CLI）** | [en/memshellutil.md](en/memshellutil.md) | [zh/memshellutil.md](zh/memshellutil.md) |

**配置**：统一由 `configutil` 加载；`[notify]` / `[img]` / `[memshell]` 段见对应模块文档，摘要见根 README。
