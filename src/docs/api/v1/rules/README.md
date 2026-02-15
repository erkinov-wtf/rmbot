# API v1 Rules (`/rules/`)

## Scope
Documents rules configuration governance endpoints for read/update/history/rollback workflows.

## Access Model
- `GET` endpoints: `super_admin`, `ops_manager`.
- `PUT` and rollback actions: `super_admin`.

## Endpoint Reference

### `GET /api/v1/rules/config/`
- Returns active rules state (version metadata + active config payload + cache token).

### `PUT /api/v1/rules/config/`
- Validates and normalizes incoming config, then creates a new immutable version and activates it.
- Optional `reason` is persisted with version metadata.
- Config includes `work_session` section for pause-budget controls:
  - `daily_pause_limit_minutes`
  - `timezone`

### `GET /api/v1/rules/config/history/`
- Returns paginated append-only version history with stored diffs/checksums.
- Optional filters:
  - `version`
  - `action` (`bootstrap`, `update`, `rollback`)
  - `created_by_id`
  - `source_version`
  - `ordering` (`version`, `-version`, `created_at`, `-created_at`)
- Pagination parameters:
  - `page`
  - `per_page`

### `POST /api/v1/rules/config/rollback/`
- Creates a new rollback version that restores selected historical target version.

## Validation and Failure Modes
- Schema normalization or semantic validation failure -> `400`.
- No-op config updates are rejected -> `400`.
- Unknown `target_version` for rollback -> `404` or validation error.
- Unauthorized write role -> `403`.

## Operational Notes
- Config updates are append-only; active pointer changes but historical rows remain immutable.
- Rollback is implemented as a new version, never destructive rewrite.

## Related Code
- `api/v1/rules/urls.py`
- `api/v1/rules/views.py`
- `api/v1/rules/filters.py`
- `apps/rules/services.py`
- `apps/rules/models.py`
