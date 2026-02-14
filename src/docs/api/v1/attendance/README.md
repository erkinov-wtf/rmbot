# API v1 Attendance (`/attendance/`)

## Scope
Documents self-service attendance endpoints for daily check-in/checkout and punctuality XP side effects.

## Access Model
- All endpoints require authentication.
- Access scope is current authenticated user only.

## Endpoint Reference

### `GET /api/v1/attendance/today/`
- Reads today's attendance row for current user.
- Returns empty `data` when row does not exist.

### `POST /api/v1/attendance/checkin/`
- Creates today's attendance check-in timestamp.
- Appends punctuality XP ledger entry when rule conditions are met.

### `POST /api/v1/attendance/checkout/`
- Sets checkout timestamp for today's attendance row.

## Validation and Failure Modes
- Duplicate check-in -> `400`.
- Checkout before check-in -> `400`.
- Duplicate checkout -> `400`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- XP amount and punctuality thresholds are rules-driven.
- Attendance writes are append-safe in XP ledger through immutable entry model constraints.

## Related Code
- `api/v1/attendance/urls.py`
- `api/v1/attendance/views.py`
- `apps/attendance/services.py`
- `apps/gamification/services.py`
