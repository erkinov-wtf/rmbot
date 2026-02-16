# Bot Runtime and Lifecycle

## Scope
Documents aiogram runtime assembly, lifecycle entrypoints, webhook intake path, and middleware contract.

## Runtime Composition
- `create_bot_bundle` in `bot/etc/loader.py` assembles:
  - `Bot` (parse mode from settings)
  - `Dispatcher` (in-memory FSM storage)
  - DI `Container` (settings/logger/i18n)
- `bot/runtime.py` keeps a process-global lazy `BotBundle` behind an async lock.
- Root router includes onboarding/fallback handlers and technician ticket handlers (`/queue` + callback actions).

## Execution Flows

### Polling flow (`python manage.py runbot`)
1. Validate `BOT_TOKEN`.
2. Build or reuse singleton bundle.
3. Start dispatcher polling loop.
4. Close bot session on shutdown.

### Webhook admin flow (`python manage.py botwebhook set|delete`)
- `set`: validates token/base URL and registers Telegram webhook (optional secret token).
- `delete`: removes configured webhook from Telegram.

### Webhook request flow (`POST /bot/webhook/`)
1. Verify request method is `POST`.
2. Enforce `BOT_MODE=webhook`.
3. Validate `X-Telegram-Bot-Api-Secret-Token` when configured.
4. Parse JSON and convert to aiogram `Update`.
5. Dispatch update through aiogram dispatcher.

## Invariants and Contracts
- Middleware order is stable and behavior-sensitive:
  1. `ErrorMiddleware` (outer)
  2. `I18nMiddleware`
  3. `DIMiddleware`
  4. `AuthMiddleware`
- `AuthMiddleware` resolves identity from aiogram update context (`data["event_from_user"]`) first, then falls back to event/message objects, so update-level middleware execution still authenticates `/queue` and callback actions correctly.
- `get_bundle()` is concurrency-safe; only one bundle instance exists per process.
- `close_bundle()` must release HTTP resources and reset runtime singleton.

## Failure Modes
- Missing/invalid bot credentials prevent polling/webhook setup.
- Invalid webhook secret token returns request rejection.
- Malformed webhook payloads are rejected before dispatcher execution.

## Operational Notes
- FSM storage is in-memory and not restart-safe.
- Webhook mode is preferred for multi-worker deployments.
- Polling can be started even when mode is not `polling` (warning-oriented behavior).

## Related Code
- `bot/etc/loader.py`
- `bot/runtime.py`
- `bot/webhook/views.py`
- `bot/management/commands/runbot.py`
- `bot/management/commands/botwebhook.py`
