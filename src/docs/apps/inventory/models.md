# Inventory Models (`apps/inventory/models.py`)

## Scope
Defines inventory entities used by ticket intake and analytics.

## Model Inventory
- `Inventory`: top-level grouping (place/warehouse for items).
- `InventoryItemCategory`: dynamic classification for inventory items.
- `InventoryItemPart`: reusable part catalog attached to items.
- `InventoryItem`: primary fleet entity used by ticket lifecycle.

## Invariants and Constraints
- `Inventory.name`, `InventoryItemCategory.name`, and `InventoryItemPart.name` are unique.
- `InventoryItem.serial_number` is unique.
- `InventoryItem` requires `inventory` + `category`; `parts` is optional M2M.
- Status/activity indexed for fleet analytics queries.

## Lifecycle Notes
- Inventory items may be created via admin/API or ticket-intake confirm-create path.
- `InventoryItem` status transitions expose model-level helpers (`mark_in_service`, `mark_ready`) so workflow services do not mutate status fields directly.

## Operational Notes
- Inactive/non-ready inventory items are excluded from ready-fleet availability counters.
- Query-focused access goes through `InventoryItem.domain` and related domain managers for alive-only lookups and shared retrieval rules.

## Related Code
- `apps/inventory/services.py`
- `apps/inventory/managers.py`
- `api/v1/inventory/views.py`
