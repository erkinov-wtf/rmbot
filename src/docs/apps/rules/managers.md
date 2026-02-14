# Rules Managers (`apps/rules/managers.py`)

## Scope
Defines domain query and creation helpers for immutable rules versions and the singleton active state.

## Manager Inventory
- `RulesConfigVersionQuerySet` + `RulesConfigVersionDomainManager`
- `RulesConfigStateDomainManager`

## Execution Notes
- Version manager responsibilities:
  - Next version-number generation.
  - Version lookup by explicit number.
  - Latest-version listing with related actor/source rows.
  - Immutable version row creation via `create_version_entry`.
- State manager responsibilities:
  - Singleton row locking (`get_singleton_for_update`).
  - Singleton bootstrap creation (`create_singleton`).
  - Active-state retrieval with related active version + creator (`get_with_related`).

## Invariants and Contracts
- Version numbers are monotonically incremented from DB state.
- State manager assumes a singleton row contract enforced by model constraint.
- Managers do not own rules validation/caching concerns; they only own persistence lookup/write helpers.

## Related Code
- `apps/rules/models.py`
- `apps/rules/services.py`
