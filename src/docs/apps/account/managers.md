# Account Managers (`apps/account/managers.py`)

## Scope
Provides domain query and identity-preparation helpers for onboarding and moderation flows.

## Manager Inventory
- `UserManager`: auth manager plus pending-user preparation helpers.
- `AccessRequestDomainManager`: pending/approved/rejected request lookup helpers.
- `TelegramProfileDomainManager`: Telegram profile upsert/link helpers with soft-delete revival.

## Execution Notes
- `UserManager.create_pending_user` centralizes username collision handling and pending user creation.
- `AccessRequestDomainManager` consolidates Telegram-id scoped request lookups used by bot onboarding.
- `AccessRequestDomainManager.latest_active_with_user` provides recovery lookup for active user relinking during bot auth.
- `TelegramProfileDomainManager.link_to_user` and `upsert_from_telegram_user` provide one-path identity reconciliation.

## Invariants and Contracts
- Phone uniqueness checks are enforced before pending-user updates/creates.
- Domain managers intentionally use `all_objects` where soft-deleted rows must be considered during reconciliation.

## Related Code
- `apps/account/models.py`
- `apps/account/services.py`
- `api/v1/account/views.py`
- `bot/routers/start/__init__.py`
