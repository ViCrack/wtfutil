# wtfutil.notifyutil

多通道通知、`push_config`、`send` 聚合推送。

```python
from wtfutil import send, push_config, feishu_bot
```

## 配置 push_config

加载顺序（后者覆盖前者）：

1. 内置默认值
2. `wtfconfig.ini` 的 `[notify]` 段
3. 环境变量（**最高**）

查找路径与 `get_resource("wtfconfig.ini")` 一致：当前工作目录 → `resource/wtfconfig.ini` → `~/wtfconfig.ini`。

常用键示例：`CONSOLE`, `BARK_PUSH`, `FEISHU_KEY`, `FEISHU_SECRET`, `DD_BOT_TOKEN`, `DD_BOT_SECRET`, `TG_BOT_TOKEN`, `TG_USER_ID`, `SMTP_SERVER`, `SMTP_EMAIL`, `SMTP_PASSWORD`, `SHOWDOC_KEY`, `WEBHOOK_URL`, `WEBHOOK_METHOD`, `WEBHOOK_CONTENT_TYPE`, `WEBHOOK_BODY`, `HITOKOTO`, `SKIP_PUSH_TITLE` 等（完整列表见 `notifyutil.py` 默认值与 `wtfconfig.ini.example`）。

```python
from wtfutil import send, push_config

send("标题", "正文")
push_config["FEISHU_KEY"] = "xxx"
push_config["CONSOLE"] = "true"
```

单通道：

```python
from wtfutil import feishu_bot, telegram_bot

feishu_bot("告警", "磁盘使用率 90%")
telegram_bot("告警", "任务失败")
```

## send(title, content)

并发调用所有已配置通道。内容为空则记录错误；可通过 `HITOKOTO` 追加一言；`SKIP_PUSH_TITLE` 可跳过标题。

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
| PushDeer / PushPlus / Qmsg | `pushdeer`, `pushplus_bot`, `qmsg_bot` |
| 企业微信 | `wecom_app`, `WeCom`, `wecom_bot` |
| Telegram | `telegram_bot` |
| SMTP / ShowDoc / 自定义 Webhook | `smtp`, `showdoc`, `custom_notify` |
| 其它 | `aibotk`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `notifyx`, `chronocat`, `chat` |

签名均为 `(title: str, content: str)` 形式（`console` 等略有差异见源码）。
