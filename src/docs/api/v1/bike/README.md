# API v1 Bikes (`/bikes/`)

## Scope
Documents generic bike CRUD endpoints and rich list filters for fleet inventory queries.

## Access Model
- `GET /api/v1/bikes/` and `GET /api/v1/bikes/{id}/`: any authenticated user.
- `POST /api/v1/bikes/`, `PUT/PATCH/DELETE /api/v1/bikes/{id}/`: roles `super_admin`, `ops_manager`, `master`.

## Endpoint Reference

### `GET /api/v1/bikes/`
- Lists fleet bikes.
- Supports optional filters:
  - `q` (BikeCode lookup, min 2 chars; suggestion-style matching merged into list)
  - `bike_code` (exact code match)
  - `status`
  - `is_active`
  - `has_active_ticket`
  - `created_from` / `created_to` (`YYYY-MM-DD`)
  - `updated_from` / `updated_to` (`YYYY-MM-DD`)
  - `ordering` (`created_at`, `-created_at`, `updated_at`, `-updated_at`, `bike_code`, `-bike_code`, `status`, `-status`)

### `POST /api/v1/bikes/`
- Registers a bike in inventory.
- Enforces normalized, unique `bike_code` format (`RM-[A-Z0-9-]{4,29}`).

### `GET /api/v1/bikes/{id}/`
- Returns a single bike by ID.

### `PUT/PATCH /api/v1/bikes/{id}/`
- Updates bike fields (including `bike_code`, `status`, `is_active`).

### `DELETE /api/v1/bikes/{id}/`
- Soft-deletes a bike record.

## Validation and Failure Modes
- Invalid/duplicate `bike_code` on create -> `400`.
- Too-short/invalid `q` or invalid filter values -> `400`.
- Unauthorized write roles (create/update/delete) -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Archived bike-code conflicts are handled at ticket intake flow (restore-required behavior), not via implicit recreate.
- Ticket intake typo-control still uses internal bike suggestion logic from domain services.

## Related Code
- `api/v1/bike/urls.py`
- `api/v1/bike/views.py`
- `api/v1/bike/filters.py`
- `apps/bike/models.py`
- `apps/ticket/services_workflow.py`
