# API v1 Attendance (`/attendance/`)

## Scope
Documents manager-operated attendance endpoints for technician check-in/checkout and filtered day-level attendance reads.

## Access Model
- All endpoints require authentication.
- Only highest operational roles can access:
  - `super_admin`
  - `ops_manager`
  - `master`

## Endpoint Reference

### `GET /api/v1/attendance/records/`
- Returns paginated attendance records for a selected `work_date` (defaults to current business date).
- Optional query parameters:
  - `work_date` (`YYYY-MM-DD`)
  - `user_id` (preferred)
  - `technician_id` (backward-compatible alias)
  - `punctuality` (`early`, `on_time`, `late`)
  - `ordering` (`user_id`, `-user_id`, `check_in_at`, `-check_in_at`, `created_at`, `-created_at`)
- Pagination parameters:
  - `page`
  - `per_page`
- Each row includes computed `punctuality_status`.

### `POST /api/v1/attendance/checkin/`
- Creates today's attendance check-in timestamp for selected user.
- Required JSON field: `user_id` (`technician_id` also accepted for backward compatibility).
- Appends punctuality XP transaction entry when rule conditions are met.

### `POST /api/v1/attendance/checkout/`
- Sets checkout timestamp for selected user's attendance row.
- Required JSON field: `user_id` (`technician_id` also accepted for backward compatibility).

## Validation and Failure Modes
- Duplicate check-in -> `400`.
- Checkout before check-in -> `400`.
- Duplicate checkout -> `400`.
- Missing/invalid `user_id` -> `400`.
- Invalid `work_date` or `punctuality` query values -> `400`.
- Actor without required role -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- XP amount and punctuality thresholds are rules-driven.
- Attendance writes are append-safe in XP transactions through immutable entry model constraints.

## Related Code
- `api/v1/attendance/urls.py`
- `api/v1/attendance/views.py`
- `api/v1/attendance/filters.py`
- `apps/attendance/services.py`
- `apps/gamification/services.py`
