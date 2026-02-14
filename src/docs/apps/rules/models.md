# Rules Models (`apps/rules/models.py`)

## Scope
Defines immutable rules versions and singleton active-state pointer.

## Model Inventory
- `RulesConfigAction`: version action enum (`bootstrap`, `update`, `rollback`).
- `RulesConfigVersion`: append-only config history row.
- `RulesConfigState`: singleton record pointing to active version and cache key.

## Invariants and Constraints
- `RulesConfigVersion.version` unique.
- Exactly one `RulesConfigState` row enforced by singleton flag.

## Lifecycle Notes
- Any update/rollback writes a new version, never mutating history rows.

## Operational Notes
- Consumers should use `RulesService` to respect cache and normalization contracts.

## Related Code
- `apps/rules/services.py`
- `api/v1/rules/views.py`
