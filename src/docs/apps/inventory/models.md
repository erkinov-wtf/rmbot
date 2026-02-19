# Inventory Models (`apps/inventory/models.py`)

## Scope
Defines inventory entities used by ticket intake, inventory admin workflows, and analytics.

## Model Inventory
- `Inventory`: top-level grouping (place/warehouse for items).
- `InventoryItemCategory`: dynamic classification for inventory items.
- `InventoryItemPart`: category-scoped part record reused by inventory items in the same category.
- `InventoryItem`: primary fleet entity used by ticket lifecycle.

## Invariants and Constraints
- `Inventory.name` and `InventoryItemCategory.name` are unique.
- `InventoryItem.serial_number` is unique.
- Active part name uniqueness is enforced by service/serializer rules per category.
- `InventoryItem` requires `inventory` + `category`; item serializers project category-part IDs through `parts`.
- Status/activity indexed for fleet analytics queries.

## Lifecycle Notes
- Inventory items may be created via admin/API or ticket-intake confirm-create path.
- `InventoryItem` status transitions expose model-level helpers (`mark_in_service`, `mark_ready`) so workflow services do not mutate status fields directly.
- Category deletion is orchestrated by service layer: deletion is blocked while active items reference the category; otherwise category-level parts are archived first to satisfy `PROTECT` constraints.

## Operational Notes
- Inactive/non-ready inventory items are excluded from ready-fleet availability counters.
- Query-focused access goes through `InventoryItem.domain` and related domain managers for alive-only lookups and shared retrieval rules.

## Related Code
- `apps/inventory/services.py`
- `apps/inventory/managers.py`
- `api/v1/inventory/views.py`
