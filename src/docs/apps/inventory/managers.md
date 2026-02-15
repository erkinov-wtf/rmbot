# Inventory Managers (`apps/inventory/managers.py`)

## Scope
Encapsulates inventory domain queries so service/API/analytics layers reuse the same alive-only lookup rules.

## Manager Inventory
- `InventoryQuerySet` + `InventoryDomainManager`
- `InventoryItemCategoryQuerySet` + `InventoryItemCategoryDomainManager`
- `InventoryItemPartQuerySet` + `InventoryItemPartDomainManager`
- `InventoryItemQuerySet` + `InventoryItemDomainManager`

## Execution Notes
- `InventoryItem.domain.find_by_serial_number` resolves case-insensitive serial lookup against non-deleted items.
- `InventoryItem.domain.ready_active_count` centralizes stockout/availability count logic.
- `InventoryItem.domain.suggest_serial_numbers` executes staged lookup (prefix -> contains -> fuzzy) with bounded results.
- QuerySet helpers support inventory-item list filtering by serial/inventory/category/status/activity/date windows and active-ticket presence.
- Each manager exposes `get_default()` used by ticket intake/API create defaults.

## Invariants and Contracts
- `get_queryset` enforces `deleted_at IS NULL`.
- Suggestion output is deduplicated and capped by caller-provided limit.

## Related Code
- `apps/inventory/models.py`
- `apps/inventory/services.py`
- `apps/ticket/services_stockout.py`
