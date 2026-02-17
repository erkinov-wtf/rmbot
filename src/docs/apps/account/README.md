# Account App Docs

## Scope
Covers identity, role linkage, Telegram profile binding, and access-request moderation workflows.

## Navigation
- `docs/apps/account/models.md`
- `docs/apps/account/managers.md`
- `docs/apps/account/services.md`

## Maintenance Rules
- Update model docs when identity fields/constraints change.
- Update service docs when onboarding/moderation logic or notification behavior changes.

## Related Code
- `apps/account/models.py`
- `apps/account/managers.py`
- `apps/account/services.py`
- `api/v1/account/`
- `bot/routers/start/__init__.py`
