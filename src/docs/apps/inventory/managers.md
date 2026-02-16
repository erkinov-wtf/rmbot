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
- `InventoryItem.domain.ready_active_count` centralizes active ready-fleet availability logic.
- `InventoryItem.domain.suggest_serial_numbers` executes staged lookup (prefix -> contains -> fuzzy) with bounded results.
- `InventoryItemPartQuerySet.with_inventory_item` scopes parts to an owning inventory item.
- QuerySet helpers support inventory-item list filtering by serial/inventory/category/status/activity/date windows and active-ticket presence.
- `Inventory.domain` and `InventoryItemCategory.domain` expose `get_default()` used by ticket intake/API create defaults.

## Invariants and Contracts
- `get_queryset` enforces `deleted_at IS NULL`.
- Suggestion output is deduplicated and capped by caller-provided limit.

## Related Code
- `apps/inventory/models.py`
- `apps/inventory/services.py`
