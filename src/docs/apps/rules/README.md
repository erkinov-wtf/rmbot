# Rules App Docs

## Scope
Covers dynamic rules validation, immutable version history, singleton active-state lifecycle, and cache-aware activation flow.

## Navigation
- `docs/apps/rules/models.md`
- `docs/apps/rules/managers.md`
- `docs/apps/rules/services.md`

## Maintenance Rules
- Update docs when rules schema/normalization changes.
- Keep manager/model/service responsibilities explicit whenever rules lifecycle logic is moved across layers.

## Related Code
- `apps/rules/models.py`
- `apps/rules/managers.py`
- `apps/rules/services.py`
- `api/v1/rules/`
