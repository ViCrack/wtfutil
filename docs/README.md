# wtfutil API 文档索引

完整 API 按子模块拆分，便于查阅与 AI 索引。根目录 [README.md](../README.md) / [README_zh.md](../README_zh.md) 仅保留快速入门。

| 模块 | 英文 | 中文 |
|------|------|------|
| `wtfutil.util` | [en/util.md](en/util.md) | [zh/util.md](zh/util.md) |
| `wtfutil.httputil` | [en/httputil.md](en/httputil.md) | [zh/httputil.md](zh/httputil.md) |
| `wtfutil.fileutil` | [en/fileutil.md](en/fileutil.md) | [zh/fileutil.md](zh/fileutil.md) |
| `wtfutil.strutil` | [en/strutil.md](en/strutil.md) | [zh/strutil.md](zh/strutil.md) |
| `wtfutil.sqlutil` | [en/sqlutil.md](en/sqlutil.md) | [zh/sqlutil.md](zh/sqlutil.md) |
| `wtfutil.procutil` | [en/procutil.md](en/procutil.md) | [zh/procutil.md](zh/procutil.md) |
| `wtfutil.notifyutil` | [en/notifyutil.md](en/notifyutil.md) | [zh/notifyutil.md](zh/notifyutil.md) |
| `wtfutil.translateutil` | [en/translateutil.md](en/translateutil.md) | [zh/translateutil.md](zh/translateutil.md) |
| `wtfutil.imgutil` | [en/imgutil.md](en/imgutil.md) | [zh/imgutil.md](zh/imgutil.md) |
| `wtfutil.singleinstance` | [en/singleinstance.md](en/singleinstance.md) | [zh/singleinstance.md](zh/singleinstance.md) |

**配置**：`wtfconfig.ini` 的 `[notify]` / `[img]` 段见 [notifyutil](zh/notifyutil.md) / [imgutil](zh/imgutil.md)，摘要见根 README。

**包级导出**：`wtfutil/__init__.py` 的 `__all__` 为各子模块 `__all__` 的拼接；新增 API 时请同步对应 `docs/en/*.md` 与 `docs/zh/*.md`。
