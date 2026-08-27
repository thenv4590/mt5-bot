# MT5 TradingView Webhook Bot

FastAPI service that receives TradingView webhook alerts and executes market
orders on MetaTrader 5 (Exness) accounts.

## Features

- `POST /api/order` accepts raw `text/plain` bodies (as sent by TradingView),
  manually parses the string as JSON, then validates it with Pydantic.
- Maps `order_id` to trade actions:
  - `openLong` → BUY
  - `closeLong` → close open LONG position(s)
  - `openShort` → SELL
  - `closeShort` → close open SHORT position(s)
- `strategy` in the payload selects the strategy/account block from
  `config.json` (base capital, deviation, magic number, MT5 login/server/terminal
  path). The **symbol to trade comes from the webhook payload** (`symbol`),
  not from `config.json` — configure your TradingView alert to send the
  exact MT5 symbol name (e.g. `ETHUSD`).
- Position size: `investment = strategy.price * 1000 * order_ratio` (config's
  `price` is the base capital per strategy, in **thousands of USD**;
  `order_ratio` from the webhook scales it), `volume = investment / market_price`
  where `market_price` is the live bid/ask fetched from MT5 at order time,
  then normalized to the symbol's `volume_min` / `volume_max` / `volume_step`.
- `dryRun` mode (global in `config.json`, per-strategy override, or via
  `DRY_RUN` env var) validates and logs the order without sending it to MT5.
- MT5 password is read from `.env`, never from `config.json`.
- Structured logging to console + rotating file (`logs/app.log`).
- Optional Telegram notification per strategy for every executed order
  (success, failure, or dry run), sent after the MT5 response.

## Requirements

- Windows, with MetaTrader 5 terminal installed and logged in (or logged out
  — the app logs in using the configured account) — required only to place
  **real** orders. `dryRun: true` works anywhere the `MetaTrader5` package
  can be imported.
- Python 3.10+

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copy the example config and env files:

```bash
copy config.example.json config.json
copy .env.example .env
```

Edit `config.json`:

```json
{
  "dryRun": true,
  "strategies": {
    "eth_strategy_01": {
      "price": 1,
      "deviation": 200,
      "magic": 100001,
      "comment": "ETH Strategy 01",
      "mt5": {
        "login": 12345678,
        "server": "Exness-MT5Trial"
      },
      "telegram": {
        "enabled": true,
        "chatId": "-1001234567890"
      }
    }
  }
}
```

- `price` is the strategy's base capital, in **thousands of USD**
  (`1` = $1,000). Actual investment per signal is
  `price * 1000 * order_ratio`.
- `deviation` is the **starting** max allowed slippage (in points) for a
  market order. It is not the whole story: if MT5 rejects a fill for being
  too far from this (retcode Requote / Price Changed — the only rejections
  a fresh price can actually fix), the bot automatically retries with a
  fresh tick and a 3x wider deviation, up to **5 attempts total**, capped
  at **25x** the starting deviation (so it can't grow unbounded) and with a
  short delay between attempts so the next tick is a genuinely fresh quote
  (see `mt5_client.send_order_with_retry`). With `deviation: 200` the
  sequence is 200 → 600 → 1800 → 5000 → 5000. This keeps the first attempt
  price-protective while still giving a real, fast-moving market several
  real chances to fill — it does not *guarantee* a fill (a structural
  rejection like market-closed or trading-disabled isn't retried, since no
  amount of retrying fixes that), but it makes losing a legitimate signal
  to ordinary slippage very unlikely. Tune the starting value per symbol —
  `200` is a reasonable starting point for a volatile crypto CFD like
  ETHUSD, but forex majors typically need far less.
- `magic` is the MT5 "magic number" tagged on every order this strategy
  places, so `closeLong`/`closeShort` only ever close positions this bot
  opened (never a manual trade or another EA's position on the same
  account/symbol).
- The MT5 terminal path is **not** in `config.json`. It defaults to the
  standard Windows install location
  (`C:/Program Files/MetaTrader 5/terminal64.exe`, hardcoded in
  `app/config.py` as `DEFAULT_MT5_TERMINAL_PATH`). If your terminal is
  installed elsewhere, set `MT5_TERMINAL_PATH` in `.env` — no code change
  needed.
- `telegram` (optional, per strategy) — omit entirely to disable
  notifications for that strategy. `chatId` is the Telegram chat/group/
  channel id to notify; `botToken` is that strategy's bot token. If
  `botToken` is omitted, it falls back to `TELEGRAM_BOT_TOKEN_<STRATEGY>`
  or `TELEGRAM_BOT_TOKEN` in `.env`. See "Telegram notifications" below.
- There is no `symbol` in `config.json` — the symbol to trade comes straight
  from the webhook payload's `symbol` field, so make sure your TradingView
  alert sends the exact MT5 symbol name (e.g. `ETHUSD`), not the raw
  TradingView ticker (e.g. `ETHUSDT.P`), unless they happen to match.
- `dryRun` can be set per-strategy too (overrides the global value); the
  `DRY_RUN` env var overrides both. Dry run still connects to MT5 to read
  the live bid/ask for an accurate volume estimate — it only skips sending
  the actual order.

Edit `.env`:

```
MT5_PASSWORD_ETH_STRATEGY_01=your-mt5-password
LOG_LEVEL=INFO
LOG_FILE=logs/app.log
```

The MT5 password env var name is `MT5_PASSWORD_<STRATEGY_KEY_UPPERCASED>`,
so a strategy named `eth_strategy_01` needs `MT5_PASSWORD_ETH_STRATEGY_01`.

## Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## TradingView alert setup

- Webhook URL: `https://your-host/api/order`
- Message body (raw text, TradingView sends this as `text/plain`):

```json
{
  "symbol": "{{ticker}}",
  "price": "{{strategy.order.price}}",
  "alert_name": "{{alert_name}}",
  "timenow": "{{timenow}}",
  "order_id": "{{strategy.order.comment}}",
  "order_action": "{{strategy.order.action}}",
  "comment": "{{strategy.order.comment}}",
  "alert_message": null,
  "order_ratio": 1,
  "strategy": "eth_strategy_01"
}
```

- `order_id` (populated from `strategy.order.comment`) must resolve to one
  of `openLong`, `closeLong`, `openShort`, `closeShort` — set this via your
  Pine Script strategy's order comment.
- `strategy` must match a key under `strategies` in `config.json`.
- `symbol` (`{{ticker}}`) is used as-is as the MT5 symbol to trade. If your
  MT5 broker's symbol name differs from TradingView's ticker (e.g.
  `ETHUSDT.P` vs `ETHUSD`), hardcode the correct MT5 symbol in the alert
  message instead of using `{{ticker}}`.

## Telegram notifications

Each strategy can notify a Telegram chat after every executed order
(success, failure, or dry run).

1. Create a bot via [@BotFather](https://t.me/BotFather), get its token.
2. Add the bot to the chat/group/channel you want notified, then get the
   chat id (e.g. message the bot and check
   `https://api.telegram.org/bot<TOKEN>/getUpdates`, or use a helper bot
   like @userinfobot / @getidsbot for a personal chat/group id — channel
   ids and group ids are usually negative numbers).
3. In `config.json`, add a `telegram` block to the strategy:
   ```json
   "telegram": {
     "enabled": true,
     "botToken": "123456789:AAExampleBotTokenXXXXXXXXXXXXXXXXXXX",
     "chatId": "-1001234567890"
   }
   ```
4. Omit `telegram` entirely (or set `"enabled": false`) to disable
   notifications for that strategy.
5. Optional: instead of putting `botToken` in `config.json`, you can leave
   it out and set `TELEGRAM_BOT_TOKEN=<token>` in `.env` as a shared
   fallback (or `TELEGRAM_BOT_TOKEN_<STRATEGY_KEY>` for one specific
   strategy). A `botToken` set in `config.json` always takes precedence.

Notification failures (bad token, network error, etc.) are logged as
warnings and never affect the order result returned to TradingView.

Message format (first line, then a few detail lines):

```
✅ ETHUSD-openLong: 4.125,10
Strategy: eth_strategy_01
Volume: 0.24
Ticket: 123456789
Chi tiết: Request executed
```

The header line is `<symbol>-<action>: <fill price>`, numbers formatted
Vietnamese-style (`.` for thousands, `,` for decimals). A trailing `.P`
(TradingView's perpetual-futures suffix, e.g. `ETHUSDT.P`) is stripped from
the displayed symbol. The status emoji is `✅` success / `❌` failure / `🧪`
dry run.

`/api/order` has no built-in authentication — anyone who knows the URL can
call it. If you expose the server to the internet, restrict access at the
network level (firewall, VPN, or a reverse proxy in front of it).

## Request/response examples

Request:

```
POST /api/order
Content-Type: text/plain

{"symbol":"ETHUSD","price":"4123.45","order_id":"openLong","order_ratio":1,"strategy":"eth_strategy_01"}
```

Success response (dry run):

```json
{
  "success": true,
  "dry_run": true,
  "strategy": "eth_strategy_01",
  "symbol": "ETHUSD",
  "action": "openLong",
  "volume": 1.0,
  "price": 4123.45,
  "order_ticket": null,
  "message": "Dry run: no order sent to MT5"
}
```

Error responses use a `{"error": "<code>", "detail": ...}` shape with an
appropriate HTTP status:

| Status | error                    | Cause                                   |
|--------|--------------------------|------------------------------------------|
| 400    | `invalid_json`           | Body is not valid JSON                   |
| 400    | `invalid_payload`        | JSON body is not an object                |
| 422    | `validation_error`       | Missing/invalid fields (Pydantic)         |
| 400    | `unknown_strategy`       | `strategy` not found in `config.json`     |
| 400    | `config_error`           | Missing MT5 password / bad config          |
| 502    | `order_execution_failed` | MT5 connection/order error                |
| 500    | `internal_error`         | Unexpected server error                    |

## Tests

```bash
pytest -q
```

Tests fake the `MetaTrader5` module (installed via `sys.modules`) so the
full suite runs without a real MT5 terminal, on any OS. Covers:

- payload parsing/validation (`tests/test_schemas.py`)
- volume normalization and order-building logic (`tests/test_order_service.py`)
- the HTTP webhook, including raw `text/plain` parsing and error paths
  (`tests/test_webhook.py`)

## Project layout

```
app/
  main.py            FastAPI app, /api/order endpoint, raw-body parsing
  schemas.py          Pydantic models for the TradingView payload
  config.py            config.json + .env loading, per-strategy lookups
  mt5_client.py         thin wrapper around the MetaTrader5 package
  order_service.py      order sizing, open/close logic, dry-run handling
  logging_config.py     console + rotating file logging
config.example.json    example config (copy to config.json)
.env.example            example secrets file (copy to .env)
tests/                  pytest suite with a faked MetaTrader5 module
```

## Notes / caveats

- The `MetaTrader5` Python package maintains a single connection per
  process. If you run multiple strategies against different MT5 terminal
  installations/accounts, the app reconnects (`mt5.initialize(...)`) before
  each order if the target account differs from the currently connected one.
- `closeLong` / `closeShort` close **all** open positions on the webhook's
  `symbol` that match the strategy's `magic` number and the requested side —
  not a specific ticket, since TradingView alerts don't carry one.
- Position sizing: `investment = config.price * 1000 * order_ratio`,
  `volume = investment / market_price`, where `market_price` is the live
  ask (for opens/longs) or bid (for opens/shorts, and closes) fetched from
  MT5 at order time — not the `price` field in the webhook payload, which is
  only used for logging/context. Volume is then normalized against the
  symbol's `volume_min/max/step`.
- Dry-run mode still opens a real MT5 connection to read live bid/ask (so it
  can report a realistic volume), it just skips `order_send`.
