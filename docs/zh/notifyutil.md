# wtfutil.notifyutil

多通道通知、`push_config`、`send` 聚合推送。

```python
from wtfutil.notifyutil import feishu_bot, push_config, send
```

## 配置 push_config

加载顺序（后者覆盖前者）：

1. 内置默认值
2. `wtfconfig.ini` 的 `[notify]` 段
3. 环境变量（**最高**）

查找路径与 `get_resource("wtfconfig.ini")` 一致：当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。由 [`configutil`](configutil.md) 统一加载；`send` 前会检查 ini 的路径和 mtime，只有文件签名变化时才重新合并配置并重建启用通道列表。这不是持续监视，也不会因为普通 dict 赋值自动触发通道列表重建。

常用键示例：`CONSOLE`, `BARK_PUSH`, `FEISHU_KEY`, `FEISHU_SECRET`, `DD_BOT_TOKEN`, `DD_BOT_SECRET`, `TG_BOT_TOKEN`, `TG_USER_ID`, `SMTP_SERVER`, `SMTP_EMAIL`, `SMTP_PASSWORD`, `SHOWDOC_KEY`, `CMCC_NEWMSG_KEY`, `CMCC_NEWMSG_TO`, `WEBHOOK_URL`, `WEBHOOK_METHOD`, `WEBHOOK_CONTENT_TYPE`, `WEBHOOK_BODY`, `HITOKOTO`, `SKIP_PUSH_TITLE` 等（完整列表见 `notifyutil.py` 默认值与 `wtfconfig.ini.example`）。

```python
from wtfutil.notifyutil import send

send("标题", "正文")
```

文件签名未变时，`send` 会保留运行时写入的 `push_config`，但已建立的通道列表不会因后续 dict 赋值自动更新。因此不要把直接修改 `push_config` 描述为热更新；需要启用新通道时，应在进程启动前通过 ini 或环境变量配置。

单通道：

```python
from wtfutil.notifyutil import feishu_bot, telegram_bot

feishu_bot("告警", "磁盘使用率 90%")
telegram_bot("告警", "任务失败")
```

## send(title, content)

并发调用所有已配置通道。每个工作线程独立创建并关闭 HTTP Session，不在线程间共享可变的 Requests 状态；单个通道异常只记录日志，不阻断其它通道完成。内容为空则记录错误；可通过 `HITOKOTO` 追加一言，一言调用失败时会记录日志并继续发送原始通知；`SKIP_PUSH_TITLE` 可跳过标题。

代码内置的公网 PushPlus 与 AIOps 地址仅使用 HTTPS，不会回退到明文 HTTP；用户显式配置的本机服务和 HTTP 代理地址仍受支持。

## one()

一言（Hitokoto），可单独调用或由 `send` 按配置追加。

## 单通道函数

均可单独调用；是否生效取决于 `push_config` / 环境变量。

| 通道 | 函数 |
|------|------|
| Bark | `bark` |
| 控制台 | `console` |
| 钉钉 | `dingding_bot` |
| 飞书 | `feishu_bot`, `feishu_text`, `feishu_richtext` |
| CQHTTP | `go_cqhttp` |
| Gotify / iGot / Server酱 | `gotify`, `iGot`, `serverJ` |
| PushDeer / PushPlus / Qmsg | `pushdeer`, `pushplus_bot`, `qmsg_bot`（PushPlus/推送加需收费实名认证，不推荐优先使用） |
| 企业微信 | `wecom_app`, `WeCom`, `wecom_bot` |
| Telegram | `telegram_bot` |
| SMTP / ShowDoc / 自定义 Webhook | `smtp`, `showdoc`, `custom_notify` |
| 中国移动新消息 | `cmcc_newmsg`（仅中国移动号；见下方教程） |
| 其它 | `aibotk`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `notifyx`, `chronocat`, `chat` |

签名均为 `(title: str, content: str)` 形式（`console` 等略有差异见源码）。

## 中国移动新消息 `cmcc_newmsg`

给自己的中国移动手机号推文本，正文会直接出现在系统「5G 消息 / 新消息」里，无需 PushPlus 代发。

官方链路是 **WSS 双向**：同一条 `wss://` 连接既能收手机上行，也能把文本发回会话。本通道只做通知——连上、鉴权、发一条、短等结果、断开；不会常驻收消息，也不会当聊天机器人。连上时若服务端排队了入站消息，会用来解析会话对端 `to`。

**不要和常驻 OpenClaw / 新消息ClawBot 机器人共用同一个 Channel API Key。** 短连接会把排队入站读走，只用来学 `from`，不会转发给机器人。

### 申领 Channel API Key

1. 用 **中国移动** 号码打开系统短信，进入 **5G 消息**（有的机型叫「新消息」）。
2. 在应用号里找到 **新消息ClawBot**。
3. 打开后复制 Channel API Key，一般是 `ak_` 或 `app_` 开头。不要把 Key 写进仓库或提交到 git。

建议先用手机给该应用号发一条任意文本（例如「你好」）。服务端会把这条入站消息排队；本通道下次连接时能读到 `from`，作为会话对端。也可以把这个 id 写进 `CMCC_NEWMSG_TO`，之后发送会更快、更稳。

`CMCC_NEWMSG_TO` **不是手机号**，而是 5G 消息会话对端 id（形如一串十六进制）。只使用入站帧里的 `from`，不会把 `phone` 当对端。优先级：配置的 `CMCC_NEWMSG_TO` → 本次入站 `from` → 同一 Key 的进程缓存 → 回退用 API Key。回退到 API Key 只是兜底，可能送不达；要稳请配置 `CMCC_NEWMSG_TO`。

### 配置

`wtfconfig.ini` 的 `[notify]` 段（也可用同名环境变量，环境变量优先）：

```ini
[notify]
CMCC_NEWMSG_KEY = ak_example-key
# CMCC_NEWMSG_TO =            ; 可选，会话对端 id
# CMCC_NEWMSG_WS_URL =        ; 一般不用改，默认官方 wss
```

```python
from wtfutil.notifyutil import cmcc_newmsg, send

send("标题", "正文")
cmcc_newmsg("告警", "磁盘满了")
```

发出的文本是 `标题\n\n正文`。未配置 `CMCC_NEWMSG_TO` 且进程里还没有缓存对端时，鉴权后会多等约 2 秒收集入站 `from`。已配置或已缓存对端时不再等待。
