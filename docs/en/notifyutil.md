# wtfutil.notifyutil

Multi-channel push notifications, `push_config`, `send()` aggregator.

```python
from wtfutil.notifyutil import feishu_bot, push_config, send
```

## push_config

Load order (later wins):

1. Built-in defaults
2. `wtfconfig.ini` `[notify]` section
3. Environment variables (highest)

Located via `get_resource("wtfconfig.ini")`: cwd → `resource/wtfconfig.ini` → `~/wtfconfig.ini`. Loaded by [`configutil`](configutil.md). Before dispatch, `send` checks the selected ini path and mtime; detected file changes update `push_config` and the enabled-channel list. This is a signature check at send time, not continuous file watching.

Runtime changes to `push_config` are preserved while the ini signature is unchanged, but they do not rebuild the enabled-channel list. Use the ini file or environment variables to enable new channels.

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
CMCC_NEWMSG_KEY =
CMCC_NEWMSG_TO =
CMCC_NEWMSG_WS_URL =
WEBHOOK_URL =
WEBHOOK_METHOD = POST
WEBHOOK_CONTENT_TYPE = application/json
WEBHOOK_BODY =
```

## send(title, content)

Concurrent push to all configured channels. Each worker thread owns and closes its HTTP session, so mutable Requests state is not shared across channels. A channel failure is logged without preventing the remaining channels from completing. Empty content is logged as error. Optional Hitokoto via `HITOKOTO`; a Hitokoto failure is logged and the original notification is still sent. Use `SKIP_PUSH_TITLE` to skip a title.

Hard-coded public PushPlus and AIOps endpoints use HTTPS only and never fall back to plaintext HTTP. User-configured loopback services and HTTP proxy URLs remain supported.

```python
from wtfutil.notifyutil import send

send("Title", "Message")
```

## Channel functions

Each can be called directly (typically `title`, `content`):

`bark`, `console`, `dingding_bot`, `feishu_bot`, `feishu_text`, `feishu_richtext`, `go_cqhttp`, `gotify`, `iGot`, `serverJ`, `pushdeer`, `chat`, `pushplus_bot`, `qmsg_bot`, `wecom_app`, `WeCom`, `wecom_bot`, `telegram_bot`, `aibotk`, `smtp`, `pushme`, `pipehub`, `xtuis`, `aiops_phone`, `showdoc`, `notifyx`, `chronocat`, `custom_notify`, `cmcc_newmsg`, `one`

`pushplus_bot` (PushPlus) requires paid real-name verification and is not recommended as a first-choice channel.

```python
from wtfutil.notifyutil import feishu_bot, telegram_bot
feishu_bot("Title", "Body")
```

## China Mobile New Message (`cmcc_newmsg`)

Push plain text to your own China Mobile number via the system **5G Message / New Message** inbox. This talks to China Mobile MaaP directly; it is not PushPlus.

The official transport is a **bidirectional WSS** link: the same connection can receive inbound user messages and send outbound text. This channel only notifies — connect, authenticate, send one text frame, briefly wait for a result, then disconnect. It is not a long-lived chatbot. If the server has queued inbound messages, they are used only to learn the session peer `to`.

**Do not share the same Channel API Key with a long-lived OpenClaw / 新消息ClawBot process.** This short-lived client drains queued inbound messages to learn `from`; it does not forward them to a bot.

### Get a Channel API Key

1. On a **China Mobile** phone, open the system SMS app and enter **5G Message** (some devices label it **New Message**).
2. Open the official account **新消息ClawBot**.
3. Copy the Channel API Key (`ak_…` or `app_…`). Do not commit the key.

Send any text to that account first (for example `hello`). The server queues the inbound message; the next connection can read `from` as the session peer. You can also store that id in `CMCC_NEWMSG_TO` for faster, more reliable sends.

`CMCC_NEWMSG_TO` is **not** a phone number. It is the 5G-message session peer id. Only inbound `from` is used; `phone` is ignored. Resolution order: `CMCC_NEWMSG_TO` → inbound `from` on this connection → process cache for the same key → fall back to the API Key. Falling back to the API Key is a last resort and may not deliver; set `CMCC_NEWMSG_TO` for reliable sends.

### Configure

`[notify]` in `wtfconfig.ini` (same-named environment variables win):

```ini
[notify]
CMCC_NEWMSG_KEY = ak_example-key
# CMCC_NEWMSG_TO =
# CMCC_NEWMSG_WS_URL =
```

```python
from wtfutil.notifyutil import cmcc_newmsg, send

send("Title", "Body")
cmcc_newmsg("Alert", "Disk full")
```

The payload is `title\n\ncontent`. If no peer is configured or cached, the client waits about 2 seconds after auth for an inbound `from`.
