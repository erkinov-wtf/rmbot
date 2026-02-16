# Account Services (`apps/account/services.py`)

## Scope
Coordinates access onboarding and moderation workflows while delegating first-level state/query logic to account models/managers.

## Execution Flows
- Bot onboarding: `ensure_pending_access_request_from_bot`.
- Approval: `approve_access_request`.
- Rejection: `reject_access_request`.
- Profile linking/upsert: `upsert_telegram_profile`, `_link_telegram_profile_to_user` (delegating to `TelegramProfile.domain`).
- Bot actor resolution: `resolve_bot_actor` (upsert profile and recover active user link from access-request history when needed).

## Invariants and Contracts
- One effective pending access request per Telegram user.
- Phone uniqueness is enforced before assignment.
- Username generation is collision-safe.
- Telegram profile uniqueness by `telegram_id` is preserved.

## Side Effects
- Creates/reactivates inactive users during onboarding.
- Assigns roles and activates users on approval.
- Revives Telegram profiles and reattaches them to approved active users when legacy/missing links are detected.
- Triggers access-decision notifications via `core.services.notifications.UserNotificationService` (best effort).

## Failure Modes
- Request already resolved.
- User already linked/approved.
- Duplicate phone conflict.
- Notification delivery failures (logged, non-blocking).

## Operational Notes
- Notification transport policy lives in shared core notification service (test skip, `BOT_TOKEN` guard, on-commit dispatch).
- Integrity races on pending request creation are resolved by read-after-catch strategy.
- Service is orchestration-focused; identity patching/status transitions live on model methods.

## Related Code
- `apps/account/models.py`
- `apps/account/managers.py`
- `core/services/notifications.py`
- `bot/routers/start.py`
- `api/v1/account/views.py`
