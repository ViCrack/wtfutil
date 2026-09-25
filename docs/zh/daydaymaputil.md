# wtfutil.daydaymaputil 与 daydaymap CLI

DayDayMap Python SDK 与流式 CLI，用于查询平台已有资产。所有 SDK `count` / `search` 和 CLI 请求都强制排除**平台已标记的蜜罐**；不能识别或保证排除未标记蜜罐。地域、域名和 IPv4 默认均不限制。

`daydaymaputil.py` 提供 SDK、Key 池、聚合计数、分页与拆分，内部还负责图标和证书来源传输；`daydaymap.py` 只导出 CLI `main`。

## 快速使用

在项目目录运行 `python -m pip install -e .` 后使用 `daydaymap`，也可运行 `python -m wtfutil.daydaymap`。Key 放在外部 UTF-8 文件，一行一个。默认发现 `daydaymap_keys.txt`，不需要把 Key 写进命令行。

```bash
# Git Bash / Bash：默认搜索，逐行 JSON
daydaymap 'domain="example.com"' --fields ip,port,domain,url -o assets.jsonl

# 只计数；免费聚合优先，失败且有 Key 时可能付费回退
daydaymap --count 'domain="example.com"'

# 中国大陆（排除港澳台），只保留域名资产，URL 输出
daydaymap 'domain="example.com"' --is-china --is-domain --format url --limit 100

# stdin 自动逐行读取，模板内的输入值自动转义
printf '%s\n' example.com example.org | daydaymap --template 'domain="{}"' --format url

# 混合输入时显式指定 stdin；-o - 表示 stdout
printf '%s\n' 'port="443"' | daydaymap -q 'domain="example.com"' --query-file - -o -

# 图标文件、图标直链或网站证书，可以单独作为查询输入
daydaymap --icon-file favicon.ico --is-china
daydaymap --icon-url https://example.com/favicon.ico --count
daydaymap --cert-url https://example.com:8443 --proxy http://127.0.0.1:8080

# 来源条件与每条原始查询 AND 组合
daydaymap --query-file queries.txt --icon-file favicon.ico --key-file custom-keys.txt
```

默认搜索，使用 `--count` 计数。裸 `search` / `count` 位置词不作为查询输入；若要查询这些字面量，请使用 `-q search` / `-q count`。所有查询均强制应用蜜罐过滤。

SDK 将原始 `a || b` 包裹为 `(a || b) && ip.tag!="蜜罐"`。`build_query()` 用于预览或向其他调用者提供完整条件；`count` / `search` 接收原始查询，避免先调用 builder 再重复包裹。

PowerShell 推荐通过 UTF-8 文件避免不同版本对原生程序双引号参数的差异：

```powershell
'domain="example.com"', 'domain="example.org"' | Set-Content -Encoding utf8 queries.txt
daydaymap --query-file queries.txt --is-china --format url -o urls.txt

# 管道向 Python 传输 Unicode 时显式使用 UTF-8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Get-Content -Encoding utf8 queries.txt | daydaymap --count
```

## CLI 参数

入口：`daydaymap [QUERY] [参数]`，默认获取资产，`--count` 只输出计数。

| 参数 | 含义与默认值 |
|---|---|
| `QUERY` | 一个原始查询，使用模板时是待插值的值 |
| `-q QUERY` / `--query QUERY` | 添加查询，可重复 |
| `--count` | 只计数，免费聚合优先；有 Key 时可能付费回退。显式搜索专用参数与此选项组合会在请求前报错 |
| `--query-file FILE` | UTF-8 文件，一行一条，可重复；`-` 表示 stdin |
| `--template TEMPLATE` | 如 `domain="{}"`，占位符只能位于双引号内 |
| `--icon-file FILE` / `--icon-url URL` | 本地图标 / HTTP(S) 图片直链，互斥 |
| `--cert-url URL` | HTTPS 网站叶子证书，可与图标及查询组合 |
| `--is-china` | 添加中国大陆条件，排除港澳台；默认关闭 |
| `--is-domain` | 添加 `is_domain="true"`；默认关闭 |
| `--key-file FILE` | 外部 Key 文件，可重复 |
| `-o FILE` / `--output FILE` | 覆盖 UTF-8 输出文件；默认或 `-` 为 stdout |
| `--timeout N` | 单请求超时秒数，必须 >0，默认 30 |
| `--interval N` | SDK 请求间隔，允许 0，默认 0.5 秒 |
| `--max-retries N` | 连接建立超时、429、2006 的额外重试，0..20，默认 2 |
| `--proxy URL` | HTTP(S)/SOCKS 代理，SOCKS 安装 `wtfutil[socks]` |
| `--quiet` | 仅搜索模式：隐藏计数预检和摘要，错误仍写 stderr |
| `--fields LIST` | 搜索返回字段，逗号分隔，优先于排除字段 |
| `--exclude-fields LIST` | 搜索排除字段，逗号分隔 |
| `--page-size N` | 搜索页宽，1..10000，默认 500 |
| `-l N` / `--limit N` | 每条输入查询输出上限，默认 10000；0 无本地上限 |
| `--format {jsonl,url}` | 搜索输出格式，默认 JSONL；计数始终 JSONL |
| `--max-effort` | 超窗口时尝试一层聚合拆分，不保证全量 |
| `--max-effort-depth N` | 每条查询最多子查询数，1..1000，默认 10；不是递归深度 |
| `-h` / `--help` | 显示帮助 |

只允许搜索模式显式使用 `--fields`、`--exclude-fields`、`--page-size`、`--limit`、`--max-effort`、`--max-effort-depth`、`--format` 和 `--quiet`；`--count` 与这些参数组合会在读取 Key 或打开输出文件前报错。`--max-effort-depth` 需要同时启用 `--max-effort`。未显式提供这些参数时，搜索采用上表所列默认值。

## 输入顺序、模板与文件保护

先处理位置参数，再处理重复的 `-q`，最后按 `--query-file` 顺序逐行读取。忽略文件/stdin 首行 BOM、空行和整行 `#` 注释，按首次出现顺序去重。去重集合随不同查询数增长，但不预先加载完整文件。重复的 `--query-file -` 只消费一次 stdin。

没有显式 QUERY、`-q`、查询文件、图标或证书来源，而且 stdin 非终端时，自动读取 stdin。已有显式来源时不会隐式消费管道；需要混合时使用 `--query-file -`。输入逐条完成后才读取下一条，不等待 EOF。每条查询独立输出计数、结果和摘要，不合计不同查询的总量，也不跨输入查询去重资产。

模板作用于位置参数、`-q` 和逐行输入。例如 `domain="{}" || cert.subject.cn="{}"` 会把同一值填入两个位置。输入中的反斜杠先转成 `\\`，双引号转成 `\"`。无占位符、未知花括号、引号外的 `{}`、未闭合引号、被反斜杠转义的占位符都会在本地报错。

图标/证书只解析一次，与每条查询以括号包裹后 AND 组合；没有文本来源时可独立查询，两个指纹同时提供时也为 AND。显式文本来源为空时报告错误，不退回宽泛的指纹查询。

打开输出前验证 Key、参数、所有命名查询文件和输入路径冲突，并解析图标/证书。不能覆盖所用 Key、查询或图标文件，包括符号链接、硬链接；重定向为 stdin 的普通文件也按文件身份保护。空输入、缺失文件、非法模板或来源解析失败保留原输出。流式处理开始后发生错误则保留已写入的部分结果。`--key-file -` 读取名为 `-` 的普通文件，`-o -` 则始终表示 stdout。

## 过滤规则

所有公开 count/search 入口统一构造：

```text
(原始查询) && ip.tag!="蜜罐"
```

`--is-china` / `is_china=True` 额外添加：

```text
ip.country="CN" && ip.province!="香港" && ip.province!="澳门" && ip.province!="台湾" && ip.city!="香港" && ip.city!="澳门"
```

`--is-domain` / `is_domain=True` 添加 `is_domain="true"`。这些条件应用于免费聚合、付费回退、所有页和拆分子查询；依赖平台的标签与归属地数据，不在本地额外推断地域或蜜罐。

## 图标、证书与代理

- 图标对文件或下载得到的原始图片内容计算 MD5，生成 `web.icon="MD5"`。不做 Base64/MMH3 或像素归一化。支持 ICO、PNG、JPEG、GIF、WebP、BMP、SVG 的格式识别；最多 2 MiB、5 次 HTTP(S) 重定向，拒绝空内容和 HTML。格式识别不是完整图片解码。URL 必须是图片直链，不从 HTML 页面自动寻找 favicon。
- 证书通过 HTTPS 主机、端口、SNI 做 TLS 握手，取叶子证书 DER 字节 MD5，生成 `cert.md5="MD5"`。不向网站发送 HTTP 请求，不跟随网站跳转；路径/query 不影响采集的 TLS origin。允许自签和过期目标证书。经 HTTPS 代理采集时也允许自签代理证书；此连接仅采集证书，不携带 DayDayMap Key。平台 API 和图片下载仍校验 TLS。
- 平台字段为 MD5，但官方文档未详细保证其索引前处理/证书编码细节；实现选择原图字节与叶子 DER，需要用已知平台样本校准。动态图片、证书轮换、CDN/SNI、多证书部署和索引延迟可能造成零命中；成功采集不等于平台一定有匹配。
- 来源 URL 仅允许 HTTP(S)（证书仅 HTTPS），禁止 URL 用户信息；代理允许 HTTP、HTTPS、SOCKS5、SOCKS5H 和认证。异常不回显 URL、代理密码、响应载荷或 Key。
- 显式 `--proxy` 优先，覆盖环境代理且不受 `NO_PROXY` 绕过；否则遵循 Requests 环境/系统代理与 `NO_PROXY`。代理连接失败不退回直连。SOCKS5 本地解析目标，SOCKS5H 由代理解析。安装：`python -m pip install 'wtfutil[socks]'`。

## Key 发现、状态与重试

UTF-8 Key 文件可带 BOM，空行和整行注释忽略，保持顺序去重。示例仅使用虚构值：

```text
# 自己的外部 API Key 文件
example-key-a
example-key-b
```

CLI 凭证优先级：重复的 `--key-file` 列表 → `DAYDAYMAP_KEY_FILE` 单文件 → `DAYDAYMAP_API_KEY` 单 Key → 第一份发现的 `daydaymap_keys.txt`。默认文件依次查找当前目录、当前目录的 `resource/`、用户目录。不混入低优先级来源；首个文件为空、无效或不可读时不继续找后面的文件。没有 Key 时仅免费计数可用，搜索返回 2。仓库忽略默认 Key 文件名。

SDK 不读取上述 CLI 凭证环境变量。`load_keys()` / `DayDayMapClient.from_key_file()` 可自动发现文件；普通构造器不自动加载。凭证加载不依赖 INI 段、数据库或浏览器 Cookie。

成功请求把 Key 归还队尾。业务码 2001（无效）、2003（权限）、2004（积分不足）淘汰当前 Key，下一个 Key 重试同页；2005 为窗口限制，不轮换。2002/470 是语法/参数错误。状态仅在客户端生命周期内保留，不猜测每日额度重置。`available_keys` 包含借出和空闲的活跃 Key。

连接建立超时、429、2006 有限重试；429 使用同一 Key，遵守 Retry-After，要求等待超过 60 秒时停止并报告限流。读取超时等可能已经扣费的错误不自动重发。内部 API/web session 分离，禁用底层 POST 自动重试，拒绝重定向并校验 TLS。外部传入的 session 由调用者负责其认证、Cookie、代理和重试策略。

## 计数、分页与输出

`--count` 先请求匿名聚合 `/api/v1/raymap/search/aggregate/query`，不发送 Key。多个可用桶维度取加总最大值，包含“其他”桶，始终标记**估算**。`ip_num` 仅作 `ip_count`，不是资产总量；空/无效桶不当成零。

```json
{"query":"(domain=\"example.com\") && ip.tag!=\"蜜罐\"","total":100,"estimated":true,"source":"aggregate","ip_count":80}
```

数字仅为示例。聚合不可用且有 Key 时，CLI 和 SDK 的 `count()` 都会自动使用 `/api/v1/raymap/search/all` 的 `page=1,page_size=1,fields=ip` 获取 `data.total`，返回 `estimated=false,source=api`。**该回退可能消耗积分**，包括自动发现的 Key。语法错误或持续限流不触发回退。如果必须保证不产生付费 API 请求，请在调用 SDK 前不要给客户端提供 Key，或使用无 Key 的 CLI 计数环境（注意自动发现的 Key 文件也算提供 Key）。网页聚合行为可能变化；扣费、权限、限流以平台为准。

搜索先在 stderr 输出 `type=count` 预检对象，再输出资产，结束时输出 `type=summary`。免费预检失败就从首个正常搜索响应报告总量，不额外调用付费 count。估算为 0 也不会跳过搜索。SDK 用 `on_count(DayDayMapCount)` 回调获取同样的信息。

- stdout 仅有结果：搜索 JSONL/逐行 URL，计数 JSONL；进度和脱敏错误写 stderr。输出逐行 flush。`--quiet` 隐藏预检/摘要，仍保留错误。
- `limit` 对每条输入独立生效。0 无本地上限，不解除单查询前 10000 条的远端窗口，换 Key 也不解除窗口。
- 小 limit 缩小首次页宽，同一子查询保持页宽固定。末页请求可能多取不足一页，摘要 `fetched` 显示实际获取量。短页且 total 表示仍有后续记录时报告 `incomplete_page`，不静默跳页。
- JSONL 保留官方字段，fields 优先；URL 优先用官方 url，否则根据 service/domain/ip/port 组装（IPv6 加方括号），自动请求必要字段。
- `max_effort` 选择省份、端口、服务或图标维度做一层拆分。每条子查询保留过滤和括号，先按资产身份去重，再字段投影；能直接拆分时跳过根明细查询。分桶可能遗漏、重叠或仍超窗口，发生拆分后始终报告 `truncated=true,reason=best_effort`，不保证全量。
- 普通分页不对相同投影结果去重；同 IP 不同端口可为不同资产。分页、子查询、输入查询均串行。
- 下游管道提前关闭时立即关闭生成器、停止取后续页，按 0 退出；Windows 的断管 EINVAL 也处理，普通文件/权限错误仍失败。Ctrl+C 保留部分输出。

摘要字段：`query,total,estimated,returned,fetched,queries,truncated,limit_reached,reason,keys_remaining`。`queries` 是执行的根/子查询数，不是 HTTP 请求数；`returned` 是交给调用者的记录数，不保证消费者已持久化。

| 退出码 | 含义 |
|---|---|
| 0 | 正常完成，或下游正常提前关闭 |
| 1 | 网络、来源、响应、文件或免费聚合不可用 |
| 2 | 参数/语法错误、空输入或缺少必需 Key |
| 3 | Key 全部耗尽或不可用 |
| 4 | 截断/不完整结果，包括 limit、远端窗口、最大努力拆分 |
| 130 | 用户中断 |

批量遇到错误立即停止并保留部分输出；正常执行但任一查询截断，最终返回 4。

## Python SDK

```python
from wtfutil.daydaymaputil import DayDayMapClient, DayDayMapError, query_from_icon, query_from_certificate

icon = query_from_icon('favicon.ico')
cert = query_from_certificate('https://example.com:8443', proxy='http://127.0.0.1:8080')
with DayDayMapClient.from_key_file(timeout=30, interval=0.5) as client:
    print(client.count(icon, is_china=True).to_dict())
    try:
        for asset in client.search(cert, is_domain=True, limit=100,
                                   on_count=lambda result: print(result.to_dict())):
            print(asset)
    except DayDayMapError as error:
        print(error.reason, error.code)
    if client.last_summary is not None:
        print(client.last_summary.to_dict())
```

| 公开 API | 说明 |
|---|---|
| `DEFAULT_BASE_URL` | 默认平台根地址常量 |
| `build_query(query, *, is_china=False, is_domain=False)` | 纯查询构造器，必加蜜罐排除，返回 str |
| `query_from_icon(path=None, *, url=None, timeout=30, proxy=None)` | 恰好一个图标来源，返回原始 `web.icon` 条件 |
| `query_from_certificate(url, *, timeout=30, proxy=None)` | HTTPS 叶子 DER MD5，返回原始 `cert.md5` 条件 |
| `find_key_file()` | 返回第一份默认文件 Path 或 None |
| `load_keys(path=None)` | 校验、去重并返回 list[str]；无默认文件返回 [] |
| `DayDayMapClient(keys=(), *, session=None, web_session=None, timeout=30, interval=0.5, max_retries=2, retry_backoff=1, proxy=None)` | keys 为单个字符串或序列；普通构造器不发现文件 |
| `DayDayMapClient.from_key_file(path=None, **kwargs)` | 文件加载便捷构造，支持自动发现 |
| `client.count(query, *, is_china=False, is_domain=False)` | 返回 DayDayMapCount；固定聚合优先、必要时自动回退 |
| `client.search(query, *, fields=None, exclude_fields=None, page_size=500, limit=10000, max_effort=False, max_effort_depth=10, is_china=False, is_domain=False, on_count=None)` | 返回 dict 生成器，迭代时执行请求 |
| `client.available_keys` / `client.last_summary` | 活跃 Key 数 / 最近已启动搜索的摘要，初始为 None |
| `client.close()` / 上下文管理器 | 仅关闭内部创建的 session |
| `DayDayMapCount` | 不可变计数对象，含 query/total/estimated/source/ip_count 与 to_dict() |
| `DayDayMapSearchSummary` | 搜索摘要，字段见上，支持 to_dict() |
| `DayDayMapError` | 脱敏 reason/code/status_code/to_dict()，来源错误也用此类型 |

参数错误抛 `ValueError`，来源失败抛 `DayDayMapError`（如 `icon_file`、`icon_download`、`invalid_icon`、`certificate_fetch`、`proxy_dependency`）。调用方提前停止遍历时应关闭生成器，保证摘要及时更新。

## 本地验证与参考

```bash
python -W error::ResourceWarning -m unittest tests.test_daydaymap tests.test_daydaymap_inputs tests.test_daydaymap_transport tests.test_daydaymap_pipeline tests.test_public_api -q
python -m wtfutil.daydaymap --help
```

默认不请求真实平台。TLS/HTTP CONNECT/HTTPS 代理/SOCKS 测试使用临时证书和本地服务；证书生成需要 OpenSSL，SOCKS 需要 PySocks，缺失时对应测试跳过。子进程管道测试使用本地 API 和明显虚构的 Key。

- [官方语法](https://www.daydaymap.com/help/document?type=syntax-search)
- [官方数据 API](https://www.daydaymap.com/help/document?type=api-data)
- [官方返回字段](https://www.daydaymap.com/help/document?type=api-filed)
