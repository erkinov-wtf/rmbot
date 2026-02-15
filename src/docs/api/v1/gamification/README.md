# API v1 XP (`/xp/`)

## Scope
Documents XP ledger read endpoint used by user history and operational auditing flows.

## Access Model
- Authentication required.
- Cross-user filtering is restricted to `super_admin` and `ops_manager`.

## Endpoint Reference

### `GET /api/v1/xp/ledger/`
- Lists append-only XP ledger entries with pagination.
- Pagination parameters:
  - `page`
  - `per_page`
- Supports filtering by:
  - `user_id`
  - `ticket_id`
  - `entry_type` (`attendance_punctuality`, `ticket_base_xp`, `ticket_qc_first_pass_bonus`)
  - `reference` (contains match)
  - `created_from` / `created_to` (`YYYY-MM-DD`)
  - `amount_min` / `amount_max`
  - `ordering` (`created_at`, `-created_at`, `amount`, `-amount`)

## Validation and Failure Modes
- Invalid numeric/filter values -> `400`.
- Non-privileged cross-user lookup (`user_id` other than requester) -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Ledger rows are append-only and should be treated as immutable audit state.
- Query results are consumed by progression flows and operator investigations.

## Related Code
- `api/v1/gamification/urls.py`
- `api/v1/gamification/filters.py`
- `api/v1/gamification/views.py`
- `apps/gamification/models.py`
- `apps/gamification/services.py`
