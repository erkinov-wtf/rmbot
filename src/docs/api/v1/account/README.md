# API v1 Users (`/users/`)

## Scope
Documents authenticated identity lookup and manager moderation endpoints for bot-created access requests.

## Access Model
- `GET /me/`: any authenticated user.
- Access-request moderation endpoints: roles `super_admin` or `ops_manager`.

## Endpoint Reference

### `GET /api/v1/users/me/`
- Returns current user profile, role slugs, and linked Telegram profile snapshot for client bootstrap.
- Profile payload includes `first_name`, `last_name`, `username`, `phone`, `level`, and no longer includes `email` or `patronymic`.

### `GET /api/v1/users/access-requests/?status=<pending|approved|rejected>`
- Lists paginated moderation queue filtered by status (default `pending`).
- Optional query parameters:
  - `status` (`pending`, `approved`, `rejected`)
  - `ordering` (`created_at`, `-created_at`, `resolved_at`, `-resolved_at`)
- Pagination parameters:
  - `page`
  - `per_page`

### `POST /api/v1/users/access-requests/{id}/approve/`
- Approves pending request, activates linked pre-created user, and optionally assigns `role_slugs`.
- Triggers Telegram decision notification (best effort).

### `POST /api/v1/users/access-requests/{id}/reject/`
- Rejects pending request and keeps linked user inactive.
- Triggers Telegram decision notification (best effort).

## Validation and Failure Modes
- Invalid `status` query value -> `400`.
- Approve/reject on non-pending request -> `400`.
- Unknown/invalid role slug on approval -> `400`.
- Unauthorized role access -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Access-request creation remains bot-only; this API only moderates existing records.
- Decision notifications are non-blocking and logged on delivery failure.

## Related Code
- `api/v1/account/urls.py`
- `api/v1/account/views.py`
- `api/v1/account/filters.py`
- `apps/account/services.py`
- `apps/account/models.py`
