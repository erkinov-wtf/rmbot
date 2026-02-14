# Config Settings Runtime

## Scope
Documents settings profile composition, feature-gated integrations, and security-relevant runtime defaults.

## Loading Strategy
- `config/settings/base.py` contains shared settings + env wiring.
- `config/settings/dev.py` and `config/settings/prod.py` overlay environment profiles.
- Entrypoints resolve defaults as:
  - `manage.py` -> `config.settings.dev`
  - ASGI/WSGI -> `config.settings.prod`

## Runtime Feature Gates
- Optional dependencies (`drf_spectacular`, `celery`, `redis`, `sentry_sdk`) alter runtime behavior only when installed/configured.
- Test execution forces deterministic defaults (cache/db/debug behavior).

## Runtime Domains
- Database: `dj_database_url` parsing with test override support.
- Cache: in-memory fallback in tests/non-Redis environments; Redis cache otherwise.
- Worker scheduling: Celery broker/result + beat schedule from environment.
- Bot/security: bot mode, webhook secret, TMA skew/TTL, replay TTL from env.
- Logging: runtime file/console logging configuration.
- Observability: optional Sentry initialization with DSN validation.

## Security Contracts
- JWT auth + global exception handler are baseline API framework defaults.
- TMA freshness and webhook secret checks are environment-driven and mandatory in hardened environments.
- Invalid Sentry DSN must not break app startup.

## Failure Modes
- Missing critical env values (DB/bot secrets) can fail startup or runtime paths.
- Redis/Celery unavailability downgrades or breaks async workloads depending on deployment topology.

## Operational Notes
- Dev and prod JWT lifetimes intentionally differ for iteration vs security posture.
- Keep env variable documentation synchronized with settings changes.

## Related Code
- `config/settings/base.py`
- `config/settings/dev.py`
- `config/settings/prod.py`
