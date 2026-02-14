# API v1 Bikes (`/bikes/`)

## Scope
Documents fleet bike inventory endpoints and bike-code suggestion endpoint used by ticket intake typo control.

## Access Model
- `GET /api/v1/bikes/` and `GET /api/v1/bikes/suggest/`: any authenticated user.
- `POST /api/v1/bikes/create/`: roles `super_admin`, `ops_manager`, `master`.

## Endpoint Reference

### `GET /api/v1/bikes/`
- Lists fleet bikes ordered by latest creation.

### `POST /api/v1/bikes/create/`
- Registers a bike in inventory.
- Enforces normalized, unique `bike_code` format (`RM-[A-Z0-9-]{4,29}`).

### `GET /api/v1/bikes/suggest/?q=<text>`
- Returns fuzzy suggestions for bike-code lookup assistance during ticket intake.
- Designed for operator typo correction before unknown-bike create path.

## Validation and Failure Modes
- Invalid/duplicate `bike_code` on create -> `400`.
- Too-short/invalid `q` for suggest endpoint -> `400`.
- Unauthorized create role -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Archived bike-code conflicts are handled at ticket intake flow (restore-required behavior), not via implicit recreate.
- Suggest endpoint is read-only and does not mutate bike inventory.

## Related Code
- `api/v1/bike/urls.py`
- `api/v1/bike/views.py`
- `apps/bike/models.py`
- `apps/ticket/services_workflow.py`
