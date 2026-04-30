# Bridges — Telegram, WeChat, Slack

## Telegram Bridge

`/telegram` turns cheetahclaws into a Telegram bot — receive messages from your phone, run the model with full tool access, and reply automatically.

<div align=center>
<img src="https://github.com/SafeRL-Lab/clawspring/blob/main/docs/telegram_demo.gif" width="850"/>
</div>

### Setup (one-time)

1. Open [@BotFather](https://t.me/BotFather) in Telegram → `/newbot` → copy the token.
2. Send any message to your new bot (e.g. "hi"), then open the URL below in your browser — replace `<TOKEN>` with your real token:

```
https://api.telegram.org/bot<TOKEN>/getUpdates
```

The response is JSON. Find `"chat"` → `"id"` — that number is your chat ID:

```json
{
  "ok": true,
  "result": [
    {
      "update_id": 100000001,
      "message": {
        "from": { "id": 987654321, "first_name": "Zhang" },
        "chat": {
          "id": 987654321,
          "type": "private"
        },
        "text": "hi"
      }
    }
  ]
}
```

> **Tip:** if `result` is empty, go back to Telegram, send another message to your bot, then refresh the URL.

3. Configure cheetahclaws (example with the values above):

```
[myproject] ❯ /telegram 7812345678:AAFxyz123abcDEF456ghiJKL789 987654321
  ✓ Telegram config saved.
  ✓ Connected to @your_bot_name. Starting bridge...
  ✓ Telegram bridge active. Chat ID: 987654321
  ℹ Send messages to your bot — they'll be processed here.
  ℹ Stop with /telegram stop or send /stop in Telegram.
```

Token and chat_id are saved to `~/.cheetahclaws/config.json`. On next launch the bridge **auto-starts** if configured — the startup banner shows `flags: [telegram]`.

### How it works

```
Phone (Telegram)                  cheetahclaws terminal
──────────────────                ──────────────────────────
"List Python files"      →        📩 Telegram: List Python files
                                  [typing indicator sent...]
                                  ⚙ Glob(**/*.py) → 5 files
                                  ⚙ response assembled
                          ←       "agent.py, tools.py, ..."
```

- **Typing indicator** is sent every 4 seconds while the model processes, so the chat feels responsive.
- **Unauthorized senders** receive `⛔ Unauthorized.` and their messages are dropped.
- **Slash command passthrough**: send `/cost`, `/model gpt-4o`, `/clear`, `/monitor`, `/agent`, etc. from Telegram and they execute in cheetahclaws.
- **Interactive menus over Telegram**: commands with interactive prompts (e.g. `/monitor` wizard, `/agent` wizard, `/permission`, `/checkpoint`) run in a background thread. The menu is sent as a Telegram message; your next reply is used as the selection.
- **Job queue & remote control**: `!jobs` / `!job <id>` / `!retry <id>` / `!cancel` — see [Remote Control](#remote-control-phone--computer).
- **`/stop` or `/off`** sent from Telegram stops the bridge gracefully.

### Photo & Voice support

You can send photos and voice messages directly to the bot — no extra commands needed.

**Photos**

Send any photo (with or without a caption). CheetahClaws downloads the highest-resolution version, encodes it as Base64, and passes it to the active vision model alongside the caption text. If no caption is provided, the default prompt is `"What do you see in this image? Describe it in detail."`.

> **Requirement:** the active model must support vision (e.g. `claude-opus-4-6`, `gpt-4o`, `gemini-2.0-flash`, or any Ollama vision model such as `llava`). Use `/model` to switch if needed.

**Voice messages & audio files**

Send a voice note (OGG) or audio file (MP3). CheetahClaws transcribes it automatically and submits the transcript as your next query. The transcription is echoed back to the chat before the model responds.

> **Requirements:**
> - **`ffmpeg`** must be installed for audio conversion (`sudo apt install ffmpeg` / `brew install ffmpeg`).
> - At least one STT backend must be available (tried in order):
>   1. `faster-whisper` — `pip install faster-whisper` (local, offline, recommended)
>   2. `openai-whisper` — `pip install openai-whisper` (local, offline)
>   3. OpenAI Whisper API — set `OPENAI_API_KEY` (cloud fallback, requires internet)
>
> If `ffmpeg` is missing, voice messages will fail with `⚠ Could not download voice message.`

### Commands

| Command | Description |
|---|---|
| `/telegram <token> <chat_id>` | Configure token + chat_id, then start the bridge |
| `/telegram` | Start the bridge using saved config |
| `/telegram status` | Show running state and chat_id |
| `/telegram stop` | Stop the bridge |

### Auto-start

If both `telegram_token` and `telegram_chat_id` are set in `~/.cheetahclaws/config.json`, the bridge starts automatically on every cheetahclaws launch:

```
╭─ CheetahClaws ────────────────────────────────╮
│  Model:       claude-opus-4-6
│  Permissions: auto   flags: [telegram]
│  Type /help for commands, Ctrl+C to cancel        │
╰───────────────────────────────────────────────────╯
✓ Telegram bridge started (auto). Bot: @your_bot_name
```

The bridge also auto-starts in **web-server mode** (`cheetahclaws --web`) — handy for headless / Docker deployments where you want the browser UI and the phone bridge in a single process. See [docs/guides/docker.md](docker.md).

---

## WeChat Bridge

<div align=center>
<img src="https://github.com/SafeRL-Lab/cheetahclaws/blob/main/docs/wechat_demo.gif" width="850"/>
</div>
<div align=center>
<center style="color:#000000;text-decoration:underline">WeChat Bridge: Control cheetahclaws from WeChat (微信)</center>
</div>

`/wechat` connects cheetahclaws to WeChat via **Tencent's iLink Bot API** — the same underlying protocol used by the official [WeixinClawBot](https://www.npmjs.com/package/@tencent-weixin/openclaw-weixin) plugin. Authenticate by scanning a QR code with your WeChat app; no manual token setup required.

### Prerequisites

**Enable the ClawBot plugin inside WeChat:**
WeChat → Me → Settings → Plugins → find and enable **ClawBot** (WeixinClawBot)

> This feature is being rolled out gradually by Tencent and may not yet be available on all accounts.

### Setup (one-time, ~30 seconds)

Run `/wechat login` in cheetahclaws. A QR code URL appears in the terminal — open it in a browser or scan it directly if you installed the `qrcode` package:

```
[myproject] ❯ /wechat login
  ℹ Fetching WeChat QR code from iLink...

  请用微信扫描以下二维码 / Scan with WeChat:

  https://liteapp.weixin.qq.com/q/7GiQu1?qrcode=ccf1fb71...&bot_type=3

(Install 'qrcode' for inline QR rendering: pip install qrcode)
  等待扫码中... / Waiting for scan...
  ✓ 微信登录成功 / WeChat authenticated (account: 3cdf6fb6d104@im.bot)
  ✓ WeChat bridge started.
  ℹ Send a message from WeChat — it will be processed here.
  ℹ Stop with /wechat stop or send /stop from WeChat.
```

Scan the QR code URL with WeChat. Once confirmed, the bridge starts immediately. Credentials (`token` + `base_url`) are saved to `~/.cheetahclaws/config.json` and reused on every subsequent launch — you only need to scan once.

> **Tip:** `pip install qrcode` renders the QR code directly in the terminal as ASCII art, so you can scan without opening a browser.

### How it works

```
Phone (WeChat)          cheetahclaws terminal
──────────────          ──────────────────────────────────
"你好"          →       📩 WeChat [o9cq80_Q]: 你好
                        [typing indicator...]
                        ⚙ model processes query
                ←       "你好！有什么我可以帮你的吗？..."
```

The bridge long-polls `POST /ilink/bot/getupdates` (35-second window) in a daemon thread. The server holds the connection until a message arrives or the window closes — normal timeouts are handled transparently. Every outbound reply echoes the peer's latest `context_token` as required by the iLink protocol.

### Features

- **QR code authentication** — scan once; credentials are saved for future launches. Expired sessions (`errcode -14`) clear saved credentials and the next `/wechat` re-triggers the QR flow automatically.
- **Typing indicator** — sent every 4 seconds while the model processes, so the chat feels responsive.
- **context_token echo** — per-peer `context_token` is cached in memory and echoed on every reply (iLink protocol requirement).
- **Slash command passthrough** — send `/cost`, `/model gpt-4o`, `/clear`, `/monitor`, `/agent`, etc. from WeChat and they execute in cheetahclaws. The result is sent back to the same WeChat conversation.
- **Interactive menu routing** — commands with interactive prompts (e.g. `/monitor` wizard, `/agent` wizard, `/permission`, `/checkpoint`) run in a background thread and route the prompt to WeChat; your next WeChat reply is used as the selection input.
- **Per-user job queue** — each WeChat user has an independent job queue; `!任务` / `!job <id>` / `!retry <id>` / `!cancel` for remote control. See [Remote Control](#remote-control-phone--computer).
- **`/stop` or `/off`** sent from WeChat stops the bridge gracefully.
- **Multi-user support** — each sender's `user_id` is tracked separately so `context_token`, job queue, and input routing stay per-peer.
- **Message deduplication** — `message_id` / `seq` dedup prevents double-processing on reconnect.

### Commands

| Command | Description |
|---|---|
| `/wechat login` | Scan QR code to authenticate and start the bridge |
| `/wechat` | Start with saved credentials; triggers QR login if none saved |
| `/wechat status` | Show running state and account ID |
| `/wechat stop` | Stop the bridge |
| `/wechat logout` | Clear saved credentials and stop the bridge |

### Auto-start

If `wechat_token` is set in `~/.cheetahclaws/config.json`, the bridge starts automatically on every cheetahclaws launch:

```
╭─ CheetahClaws ────────────────────────────────╮
│  Model:       claude-opus-4-6
│  Permissions: auto   flags: [wechat]
│  Type /help for commands, Ctrl+C to cancel        │
╰───────────────────────────────────────────────────╯
✓ WeChat bridge started.
```

Also auto-starts in `cheetahclaws --web` (Docker / headless deployments).

---

## Slack Bridge

<div align=center>
<img src="https://github.com/SafeRL-Lab/cheetahclaws/blob/main/docs/slack_demo.gif" width="850"/>
</div>
<div align=center>
<center style="color:#000000;text-decoration:underline">Slack Bridge: Control cheetahclaws from Slack</center>
</div>

`/slack` connects cheetahclaws to a Slack channel via the **Slack Web API** — no external packages required, just a Bot User OAuth Token and a channel ID. Messages are polled every 2 seconds using `conversations.history`; replies update an in-place "⏳ Thinking…" placeholder so the conversation feels responsive.

### Prerequisites

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch.
2. **OAuth & Permissions** → add **Bot Token Scopes**:
   - `channels:history` `chat:write` `groups:history` `im:history` `mpim:history` `channels:read`
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`).
4. Invite the bot to your target channel: `/invite @<bot_name>` in Slack.
5. Copy the **Channel ID** (right-click channel → **Copy Link** → the `C...` segment, or via the channel's **About** panel).

### Setup (one-time, ~2 minutes)

```
[myproject] ❯ /slack xoxb-12345-... C0123456789
  ℹ Slack credentials saved (channel: C0123456789).
  ℹ Slack authenticated as @cheetahclaws_bot
  ✓ Slack bridge started.
  ℹ Send a message in the configured Slack channel — it will be processed here.
  ℹ Stop with /slack stop or send /stop in Slack.
```

Credentials are saved to `~/.cheetahclaws/config.json` and the bridge auto-starts on every subsequent launch — you only need to configure once.

### How it works

```
Slack channel                    cheetahclaws terminal
─────────────                    ──────────────────────────────────
"List files here"      →         📩 Slack [U04ABZ]: List files here
                                 [⏳ Thinking… posted to Slack]
                                 ⚙ model processes query
                       ←         "Here are the files: …"  (placeholder updated)
```

Every 2 seconds, cheetahclaws polls `GET conversations.history?oldest=<last_ts>`. When a message arrives, a `⏳ Thinking…` placeholder is posted immediately via `chat.postMessage`, then updated in-place with the real reply via `chat.update` once the model finishes.

### Features

- **No external packages** — uses only Python's stdlib `urllib`; no `slack_sdk` or `requests` needed.
- **In-place reply update** — "⏳ Thinking…" placeholder is replaced with the actual response, keeping the channel tidy.
- **Slash command passthrough** — send `/cost`, `/model gpt-4o`, `/clear`, `/monitor`, `/agent`, etc. from Slack and they execute in cheetahclaws; results are sent back to the same channel.
- **Interactive menu routing** — `/monitor` wizard, `/agent` wizard, permission prompts, and other interactive menus route to Slack; your next message is used as the selection input.
- **Job queue & remote control**: `!jobs` / `!job <id>` / `!retry <id>` / `!cancel` — see [Remote Control](#remote-control-phone--computer).
- **Auth validation on start** — `auth.test` is called before the poll loop; invalid tokens surface a clear error immediately.
- **`/stop` or `/off`** sent from Slack stops the bridge gracefully.
- **Message deduplication** — `ts` (Slack timestamp) dedup prevents double-processing.
- **Error resilience** — after 5 consecutive connection failures the loop backs off for 30 s; auth errors (`invalid_auth`, `token_revoked`) stop the bridge with a clear message.

### Commands

| Command | Description |
|---|---|
| `/slack <token> <channel_id>` | Configure and start the bridge |
| `/slack` | Start with saved credentials |
| `/slack status` | Show running state and channel ID |
| `/slack stop` | Stop the bridge |
| `/slack logout` | Clear saved credentials and stop the bridge |

### Auto-start

If `slack_token` and `slack_channel` are set in `~/.cheetahclaws/config.json`, the bridge starts automatically on every cheetahclaws launch:

```
╭─ CheetahClaws ────────────────────────────────╮
│  Model:       claude-opus-4-6
│  Permissions: auto   flags: [slack]
│  Type /help for commands, Ctrl+C to cancel    │
╰───────────────────────────────────────────────╯
✓ Slack bridge started.
```

Also auto-starts in `cheetahclaws --web` (Docker / headless deployments).

---

## Remote Control (Phone → Computer)

All three bridges (Telegram, Slack, WeChat) include a persistent job queue and remote management commands so you can control long-running work from your phone.

### Job queue

When the AI is processing a query and a new message arrives, it is queued automatically — nothing is dropped.

```
Phone: "Run all tests"
cheetahclaws: ⏳ Queued as job #a3f2 (position 1)
              "Run all tests"
              Use !jobs to check status.

Phone: !jobs
cheetahclaws: 📊 Job Dashboard
              ────────────────────────────────────
              🔄 #b7c1  [just now]  "Run all tests" — Bash: pytest…
              ✅ #a3f2  [2m ago]    "Explain auth flow" (3 steps 18s)
              ❌ #9d0e  [5m ago]    "Fix login bug" — ModuleNotFoundError

              !job <id>  !retry <id>  !cancel
```

### Bridge commands (all three bridges)

| Command | Description |
|---|---|
| `!jobs` or `!j` or `!status` | Show job dashboard (last 8 jobs, running first) |
| `!job <id>` | Show full detail card for a job — steps, result preview, error |
| `!retry <id>` | Re-run a failed job with the same prompt |
| `!cancel` | Cancel the currently running job |
| `!cancel <id>` | Cancel a specific job by ID |

### Job tracking

Each job records:
- **Status** — queued → running → done / failed / cancelled
- **Steps** — every tool call (`Bash`, `Read`, `Edit`, …) with result preview
- **Result preview** — last 600 chars of the AI's response
- **Duration** — wall-clock seconds from start to finish

Jobs are persisted to `~/.cheetahclaws/jobs.json` (last 100 kept).

### WeChat specifics

WeChat uses **per-user queues** — each `user_id` gets an independent queue, so multiple WeChat users never block each other. All commands above are in Chinese: `!任务`, `!取消`, etc. are also accepted.

---

