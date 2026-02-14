# Account Models (`apps/account/models.py`)

## Scope
Defines identity and onboarding entities (`User`, `Role`, `TelegramProfile`, `AccessRequest`).

## Model Inventory
- `Role`: RBAC role dictionary with unique slug.
- `User`: custom auth principal with level and role relations.
- `UserRole`: through-table for user-role pairs.
- `TelegramProfile`: external Telegram identity link.
- `AccessRequest`: moderation state for onboarding.

## Invariants and Constraints
- `User.username` and `User.email` are unique.
- `User.phone` is unique when provided.
- `UserRole` enforces unique (`user`, `role`) pair.
- `TelegramProfile.telegram_id` is unique.
- Only one pending `AccessRequest` per Telegram ID via conditional unique constraint.

## Lifecycle Notes
- Users may exist inactive before approval.
- Access requests move through `pending -> approved/rejected`.
- Core state mutations now expose model methods:
  - `User.sync_pending_fields`, `User.activate_if_needed`, `User.assign_roles_by_slugs`
  - `AccessRequest.patch_pending_identity`, `mark_approved`, `mark_rejected`

## Operational Notes
- `User.level` is consumed by payroll calculations.
- Manager-backed domain lookups are used across identity reconciliation flows (`AccessRequest.domain`, `TelegramProfile.domain`).

## Related Code
- `apps/account/managers.py`
- `apps/account/services.py`
- `api/v1/account/views.py`
- `bot/routers/start.py`
