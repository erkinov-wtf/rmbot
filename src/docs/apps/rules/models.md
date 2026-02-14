# Rules Models (`apps/rules/models.py`)

## Scope
Defines immutable rules versions and singleton active-state pointer with model-level activation behavior.

## Model Inventory
- `RulesConfigAction`: version action enum (`bootstrap`, `update`, `rollback`).
- `RulesConfigVersion`: append-only config history row.
- `RulesConfigState`: singleton record pointing to active version and cache key.

## Domain Hooks
- `RulesConfigVersion.domain`:
  - version lifecycle lookup/create helpers.
- `RulesConfigState.domain`:
  - singleton lock/read helpers.

## Lifecycle Notes
- `RulesConfigState.activate_version(...)` is the first-level state transition for version activation + cache-key rotation persistence.
- Update/rollback flows still create new immutable version rows; history rows are never mutated.

## Invariants and Constraints
- `RulesConfigVersion.version` is unique.
- `RulesConfigState.singleton` enforces one state row.
- Version activation persists `updated_at` as part of state mutation.

## Operational Notes
- Model methods/managers own persistence transitions.
- `RulesService` remains the orchestration layer for validation, diffing, and cache invalidation.

## Related Code
- `apps/rules/managers.py`
- `apps/rules/services.py`
- `api/v1/rules/views.py`
