# Config Runtime Entrypoints

## Scope
Documents URL composition and ASGI/WSGI/Celery bootstrapping contracts for runtime processes.

## URL Composition
- `config/urls/base.py` mounts:
  - `/admin/`
  - `/api/`
  - `/bot/`
- Static/media URL serving is included in URL config paths.
- `config/urls/dev.py` adds debug-only routes (DRF login, debug toolbar).

## ASGI/WSGI Entrypoints
- `config/server/asgi.py` and `config/server/wsgi.py` use `config.settings.prod`.
- Runtime environment must provide env vars expected by prod profile.

## Celery Entrypoint
- `config/celery.py` initializes Celery app `config`.
- Loads Django settings under `CELERY_` namespace.
- Uses task autodiscovery across installed apps.

## Scheduling Contracts
- Beat schedule is defined in settings when Celery integration is available.
- Current periodic jobs include stockout detection, SLA evaluation, and weekly level evaluation.

## Failure Modes
- Entrypoint/profile mismatch can silently alter auth/cache/runtime behavior.
- Missing broker/backend configuration prevents Celery worker/beat startup.

## Operational Notes
- Keep URL docs in sync when adding/removing router mounts.
- Keep worker process definitions aligned with scheduled task expectations.

## Related Code
- `config/urls/base.py`
- `config/urls/dev.py`
- `config/server/asgi.py`
- `config/server/wsgi.py`
- `config/celery.py`
