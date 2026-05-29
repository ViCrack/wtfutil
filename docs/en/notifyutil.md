# wtfutil.notifyutil

Multi-channel push notifications, `push_config`, `send()` aggregator.

```python
from wtfutil import send, push_config, feishu_bot
```

## push_config

Load order (later wins):

1. Built-in defaults
2. `wtfconfig.ini` `[notify]` section
3. Environment variables (highest)

Located via `get_resource("wtfconfig.ini")`: cwd → `resource/wtfconfig.ini` → `~/wtfconfig.ini`.

```ini
[notify]
CONSOLE = true
BARK_PUSH =
FEISHU_KEY =
FEISHU_SECRET =
DD_BOT_TOKEN =
DD_BOT_SECRET =
TG_BOT_TOKEN =
TG_USER_ID =
SMTP_SERVER =
SMTP_EMAIL =
SMTP_PASSWORD =
SHOWDOC_KEY =
WEBHOOK_URL =
WEBHOOK_METHOD = POST
WEBHOOK_CONTENT_TYPE = application/json
WEBHOOK_BODY =
```

## send(title, content)

Concurrent push to all configured channels. Empty content is logged as error. Optional Hitokoto via `HITOKOTO`; `SKIP_PUSH_TITLE` to skip title.

```python
from wtfutil import send, push_config

send("Title", "Message")
push_config["FEISHU_KEY"] = "xxx"
```

## Channel functions

Each can be called directly (typically `title`, `content`):

`bark`, `console`, `dingding_bot`, `feishu_bot`, `feishu_text`, `feishu_richtext`, `go_cqhttp`, `gotify`, `iGot`, `serverJ`, `pushdeer`, `chat`, `pushplus_bot`, `qmsg_bot`, `wecom_app`, `WeCom`, `wecom_bot`, `telegram_bot`, `aibotk`, `smtp`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `showdoc`, `notifyx`, `chronocat`, `custom_notify`, `one`

```python
from wtfutil import feishu_bot, telegram_bot
feishu_bot("Title", "Body")
```
