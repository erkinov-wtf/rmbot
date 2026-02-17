# Bot Runtime and Lifecycle

## Scope
Documents aiogram runtime assembly, lifecycle entrypoints, webhook intake path, and middleware contract.

## Runtime Composition
- `create_bot_bundle` in `bot/etc/loader.py` assembles:
  - `Bot` (parse mode from settings)
  - `Dispatcher` (in-memory FSM storage)
  - DI `Container` (settings/logger)
- `bot/runtime.py` keeps a process-global lazy `BotBundle` behind an async lock.
- Root router includes class-based onboarding/fallback handlers, ticket-admin handlers (`/ticket_create`, `/ticket_review`), and technician ticket handlers (`/queue` + callback actions).
- Router modules are split by job: composition modules include entrypoint and callback sub-routers for onboarding, technician, ticket-admin, and QC flows.

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
- `I18nMiddleware` resolves locale from Telegram `language_code` dynamically, normalizes regional variants (`ru-RU`, `uz_UZ`) to supported bot locales (`en`, `ru`, `uz`), and wraps each update in `django.utils.translation.override(...)`.
- Bot handlers receive `_` from middleware, backed by Django `gettext`, so runtime language selection is per-update and per-user.
- `AuthMiddleware` resolves identity from aiogram update context (`data["event_from_user"]`) first, then falls back to event/message objects, so update-level middleware execution still authenticates `/queue` and callback actions correctly.
- `AuthMiddleware` uses `AccountService.resolve_bot_actor` to upsert/revive Telegram profiles and recover active user links from access-request history, reducing false "not registered" responses for legacy data.
- Bot routers register class-based aiogram handlers only (`MessageHandler`, `CallbackQueryHandler`) to keep routing contracts explicit and testable.
- Feature router package `__init__.py` files are composition-only; business-specific handler classes live in dedicated `entry.py` / `callbacks.py` modules.
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
- Bot translations are stored in Django locale catalogs (`locales/<lang>/LC_MESSAGES/django.po`) and compiled to `.mo` via `python manage.py compilemessages`.

## Related Code
- `bot/etc/loader.py`
- `bot/runtime.py`
- `bot/routers/start/__init__.py`
- `bot/routers/technician_tickets/__init__.py`
- `bot/routers/ticket_admin/__init__.py`
- `bot/routers/ticket_qc/__init__.py`
- `bot/webhook/views.py`
- `bot/management/commands/runbot.py`
- `bot/management/commands/botwebhook.py`
