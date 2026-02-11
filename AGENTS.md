# AGENTS.md

## Purpose
Persistent technical memory for this repository across sessions.

Use this file for:
- Actual codebase structure and conventions
- Runtime/deployment mechanics
- Reusable implementation patterns
- Current gaps and constraints

Do not store temporary task chatter here.

Companion docs:
- `PROJECT.md` is the product and business specification source of truth.
- `AGENTS.md` is the implementation and engineering source of truth.
- `PROGRESS.md` is the execution tracker and cross-session progress log.

Tracking rule:
- Use `PROGRESS.md` to track delivery status across sessions.
- Update checkboxes and session notes in `PROGRESS.md` after each meaningful implementation session.
- Keep `AGENTS.md` focused on architecture/engineering conventions, not task-by-task status updates.

## Stack Snapshot
- Backend/API: Django 5 + DRF + SimpleJWT
- Bot: Aiogram 3 (integrated into Django project)
- DB: PostgreSQL (via `dj-database-url`)
- Runtime server: ASGI (`uvicorn`)
- Container tooling: Docker + docker-compose
- Python packaging: `uv` + `pyproject.toml`

## Repository Layout
- `src/manage.py`: Django entrypoint (adds `src/apps` to `sys.path`)
- `src/config/`: project configuration (settings, urls, asgi/wsgi, middleware base)
- `src/api/`: versioned REST routes (`v1`) and endpoint modules
- `src/apps/`: domain apps (currently `account`)
- `src/core/`: shared abstractions (models, managers, API base, utils, admin base, management commands)
- `src/bot/`: aiogram runtime, routers, middlewares, webhook integration, bot commands
- `src/scripts/`: container entrypoint and healthcheck scripts
- `docs/`: deployment notes

## Configuration Patterns
- Settings split:
  - `src/config/settings/base.py`
  - `src/config/settings/dev.py`
  - `src/config/settings/prod.py`
- `manage.py` defaults to `config.settings.dev`.
- ASGI/WSGI default to `config.settings.prod`.
- `ROOT_URLCONF = "config.urls"` where `src/config/urls/__init__.py` imports `base.py`.

Important convention:
- Local apps are imported as short module names (`"account"`, `"core"`, `"api"`, `"bot"`), not `apps.account`.
- This works because `manage.py` appends `src/apps` to Python path.

## Routing Structure
- Main URL composition in `src/config/urls/base.py`:
  - `/admin/` -> Django admin
  - `/api/` -> `api.url_router`
  - `/bot/` -> `bot.webhook.urls`
- API versioning:
  - `src/api/url_router.py` -> `/v1/`
  - `src/api/v1/urls.py` -> `users/`, `auth/`, `misc/`
- Core endpoints implemented now:
  - `POST /api/v1/auth/login/`
  - `POST /api/v1/auth/refresh/`
  - `POST /api/v1/auth/verify/`
  - `GET /api/v1/misc/health/`
  - `GET /api/v1/misc/test/`

## API Response Contract
Shared API behavior is in `src/core/api/views.py` and `src/core/api/exceptions.py`.

Patterns:
- Success envelope:
  - `{"success": true, "message": "OK", "data": ...}`
- Error envelope:
  - `{"success": false, "message": "...", "error": ...}`
- Paginated lists:
  - `{"success": true, "message": "OK", "results": [...], "total_count": ..., "page": ..., "page_count": ..., "per_page": ...}`
- Global DRF exception handler is configured in settings:
  - `REST_FRAMEWORK["EXCEPTION_HANDLER"] = "core.api.exceptions.custom_exception_handler"`

Rule for new endpoints:
- Prefer inheriting from `core.api.views` base classes to keep uniform response schema.

## Data Model Patterns
- Shared base models in `src/core/models.py`:
  - `TimestampedModel` (`created_at`, `updated_at`)
  - `SoftDeleteModel` (`deleted_at`, soft-delete behavior, restore, hard-delete)
- Default manager for soft-delete models:
  - `objects` hides deleted rows (`SoftDeleteManager`)
  - `all_objects` includes all rows
- Soft-delete cascade behavior is customized via:
  - `src/core/utils/deletion.py` (`SOFT_DELETE_CASCADE`)

Current auth model:
- `AUTH_USER_MODEL = "account.User"`
- `src/apps/account/models.py` extends:
  - `AbstractBaseUser`
  - `TimestampedModel`
  - `SoftDeleteModel`

## Bot Architecture (Aiogram + Django)
- Runtime bootstrap:
  - `src/bot/etc/loader.py` builds `Bot`, `Dispatcher`, DI container, middlewares, routers
- Lifecycle singleton:
  - `src/bot/runtime.py` keeps lazy global `BotBundle` with async lock
- Entrypoints:
  - Polling mode: `python manage.py runbot`
  - Webhook management: `python manage.py botwebhook set|delete`

Middlewares (order in dispatcher):
1. `ErrorMiddleware` (outer middleware, catches handler exceptions)
2. `I18nMiddleware` (injects `_` translator by locale)
3. `DIMiddleware` (injects container object)

Routers:
- `start` router: `/start`, `/help`
- `fallback` router: unknown command handler

Webhook endpoint:
- Path: `/bot/webhook/` (`src/bot/webhook/urls.py`)
- Async Django view validates:
  - POST method
  - bot mode is `webhook`
  - `X-Telegram-Bot-Api-Secret-Token` (if configured)
  - JSON payload before feeding aiogram dispatcher

## Logging and Observability
- Central logging config in `src/config/settings/base.py`
- Custom pieces:
  - `core.utils.logging.TelegramErrorHandler` sends error logs to Telegram chat
  - `core.utils.logging.RequestContextFilter` enriches logs with request/user/ip/traceback
- Rotating files used for:
  - app logs
  - error logs
  - slow query logs

## Admin Pattern
- Base admin class:
  - `src/core/admin/admins.py` -> `BaseModelAdmin` (`unfold.admin.ModelAdmin`)
- Domain admins should inherit `BaseModelAdmin`.

## Code Generation Utility
- Custom command: `python manage.py startapp <app_name> --ver v1`
- Implemented in `src/core/management/commands/startapp.py`
- It creates both:
  - API module scaffold under `src/api/<version>/<app_name>/`
  - Domain app scaffold under `src/apps/<app_name>/`
- It also appends new app name into `LOCAL_APPS` in base settings.

## Deployment Runtime
- Container entrypoint: `src/scripts/entrypoint.sh`
- Startup flow:
1. `makemigrations`
2. `migrate`
3. `collectstatic`
4. `botwebhook set`
5. start `uvicorn config.server.asgi:application --workers 4`

Healthcheck:
- `src/scripts/healthcheck.sh` checks `GET /api/v1/health/`
- Note: current route is actually `/api/v1/misc/health/` (needs alignment).

## Environment Variables In Use
From settings and bot modules:
- Django: `DEBUG`, `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`
- Postgres: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_DB`
- Bot: `BOT_TOKEN`, `BOT_MODE`, `BOT_WEBHOOK_BASE_URL`, `BOT_WEBHOOK_PATH`, `BOT_WEBHOOK_SECRET`, `BOT_PARSE_MODE`
- i18n: `BOT_DEFAULT_LOCALE`, `BOT_FALLBACK_LOCALE`
- Log alerts: `LOGGING_TELEGRAM_BOT_TOKEN`, `LOGGING_TELEGRAM_CHAT_ID`

## Current Implementation Status (Important)
- Foundation plus major Phase A backend slices are implemented (RBAC/onboarding, bikes, tickets, work sessions, attendance, QC-linked XP, audit feed).
- Phase B is partially implemented (XP ledger baseline and append-only protections); payroll/levels/rules engine remain pending.
- Use `PROGRESS.md` as the live source for completion status and next steps.

## Conventions for Future Work
- Keep API versioning under `src/api/v1/...`.
- Place reusable framework logic in `src/core/`.
- Place business/domain models in `src/apps/<domain>/`.
- Keep bot handlers thin; move business logic into services/domain modules.
- Preserve unified response envelope for DRF APIs.
- Prefer soft-delete models for auditable entities.
- Enforce webhook secret validation in production.
- Add tests with each business-critical path (auth, transitions, ledger/payroll logic).
- Define shared enums/choices in `core/utils/constants.py` (e.g., `TextChoices`, integer choices) and import them in models/serializers.
- Generate migrations via `python manage.py makemigrations`; avoid hand-written migrations except for minimal edits after generation.
- Use explicit type hints in services and new code unless the type is trivially obvious.
- For local tests, you can set `TEST_DATABASE_URL=sqlite:///:memory:` and `LOGS_ROOT=./logs` to run `python src/manage.py test tests` without Postgres.

## Known Risks / Follow-ups
1. Healthcheck path mismatch:
   - Script checks `/api/v1/health/`
   - Existing endpoint is `/api/v1/misc/health/`
2. Entrypoint runs `makemigrations` on each startup; consider migration discipline for production.
3. No Celery/Redis worker integration is wired yet, despite project requirements.
4. No Mini App `initData` verification flow exists yet in API.
5. No RBAC role model/permissions layer beyond baseline auth user fields.
