# API v1 Core (`/auth/`, `/analytics/`, `/misc/`)

## Scope
Documents shared non-domain endpoints: authentication, analytics snapshots, and operational misc endpoints.

## Access Model
- Public endpoints: auth token operations, health, test.
- Role-gated endpoints: analytics and audit feed (`super_admin`, `ops_manager`).

## Endpoint Reference

### Auth
- `POST /api/v1/auth/login/`: username/password login, returns JWT pair.
- `POST /api/v1/auth/refresh/`: refresh token exchange for new access token.
- `POST /api/v1/auth/verify/`: token validity check.
- `POST /api/v1/auth/tma/verify/`: Telegram Mini App `init_data` verification, replay/freshness enforcement, and JWT issuance for linked users.

### Analytics
- `GET /api/v1/analytics/fleet/`: fleet availability, backlog, SLA/QC KPI aggregate snapshot.
- `GET /api/v1/analytics/team/?days=<1..90>`: per-technician productivity aggregate for selected rolling window.

### Misc
- `GET /api/v1/misc/health/`: readiness probe (raw payload).
- `GET /api/v1/misc/test/`: smoke endpoint (raw payload).
- `GET /api/v1/misc/audit-feed/`: merged chronological audit stream across key append-only entities (paginated via `page`/`per_page`).

## Validation and Failure Modes
- Invalid auth credentials/tokens -> `401`.
- Invalid TMA payload, stale/future timestamp, or replay reuse -> `400`.
- Unauthorized analytics/audit role -> `403`.
- Invalid `days` query values -> `400`.

## Operational Notes
- `health` and `test` intentionally bypass envelope wrappers for external probes.
- TMA endpoint depends on cache-backed replay lock and security env settings.

## Related Code
- `api/v1/core/urls/auth.py`
- `api/v1/core/urls/analytics.py`
- `api/v1/core/urls/misc.py`
- `api/v1/core/views/auth.py`
- `api/v1/core/views/analytics.py`
- `api/v1/core/views/misc.py`
