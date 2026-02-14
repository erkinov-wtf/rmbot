# Account Services (`apps/account/services.py`)

## Scope
Coordinates access onboarding, identity reconciliation, moderation outcomes, and Telegram notifications.

## Execution Flows
- Bot onboarding: `ensure_pending_access_request_from_bot`.
- Approval: `approve_access_request`.
- Rejection: `reject_access_request`.
- Profile linking/upsert: `upsert_telegram_profile`, `_link_telegram_profile_to_user`.

## Invariants and Contracts
- One effective pending access request per Telegram user.
- Phone uniqueness is enforced before assignment.
- Username/email generation is collision-safe.
- Telegram profile uniqueness by `telegram_id` is preserved.

## Side Effects
- Creates/reactivates inactive users during onboarding.
- Assigns roles and activates users on approval.
- Sends Telegram approval/rejection notifications (best effort).

## Failure Modes
- Request already resolved.
- User already linked/approved.
- Duplicate phone conflict.
- Notification delivery failures (logged, non-blocking).

## Operational Notes
- Notification sending is skipped for tests and missing `BOT_TOKEN`.
- Integrity races on pending request creation are resolved by read-after-catch strategy.

## Related Code
- `apps/account/models.py`
- `bot/routers/start.py`
- `api/v1/account/views.py`
