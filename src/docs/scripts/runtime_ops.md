# Runtime Scripts Operations

## Scope
Documents deployment shell scripts for web process startup and container health probing.

## Startup Sequence (`scripts/entrypoint.sh`)
1. `python manage.py migrate --noinput`
2. `python manage.py collectstatic --noinput`
3. `python manage.py botwebhook set`
4. `uvicorn config.server.asgi:application --workers 4 --lifespan off`

## Invariants and Contracts
- Script uses fail-fast semantics (`set -e`).
- Webhook setup currently runs as mandatory startup step.
- Entrypoint starts only the web ASGI process; worker processes are external.

## Healthcheck Contract (`scripts/healthcheck.sh`)
- Probes `http://localhost:8000/api/v1/misc/health/`.
- Returns exit code `0` on success and `1` on failure.

## Failure Modes
- Migration/static/webhook failure aborts startup before server bind.
- Invalid bot env configuration can fail webhook setup and block container readiness.

## Operational Notes
- Run Celery worker/beat in separate process units.
- Keep probe endpoint path synchronized with API routing changes.

## Related Code
- `scripts/entrypoint.sh`
- `scripts/healthcheck.sh`
