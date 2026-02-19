# Inventory Services (`apps/inventory/services.py`)

## Scope
Provides inventory-item serial-number normalization/validation, inventory-category deletion guard logic, and delegates query behavior to inventory managers, including list-filter orchestration for inventory item APIs.

## Execution Flows
- Normalize serial (`normalize_serial_number`).
- Validate serial format (`is_valid_serial_number`).
- Active item lookup via `InventoryItem.domain.find_by_serial_number` (`get_by_serial_number`).
- Multi-stage suggestion via `InventoryItem.domain.suggest_serial_numbers` (`suggest_serial_numbers`).
- Default relation helpers for create flows (`get_default_inventory`, `get_default_category`).
- List filter orchestration (`filter_inventory_items`) combining search/suggestion matching with state/date/ticket filters and ordering.
- Category deletion workflow (`delete_category`) that blocks deletion when items exist and archives category parts before soft-deleting the source category.

## Invariants and Contracts
- Canonical serial normalization is uppercase without whitespace.
- Format regex is strictly enforced.
- Suggestions are capped and deterministic by query strategy.

## Side Effects
- `delete_category` performs write operations: category-level part soft-delete and source-category soft delete (only when no active items reference the category).

## Failure Modes
- Invalid serial format at caller validation layer.
- Short suggestion query yields empty result.
- Category deletion fails when one or more active inventory items reference the category.

## Operational Notes
- Suggestion strategy: prefix -> contains -> fuzzy.
- Used by ticket intake typo-control flows and inventory-item list search (`q`) filtering.

## Related Code
- `apps/inventory/models.py`
- `apps/inventory/managers.py`
- `api/v1/inventory/views.py`
- `api/v1/ticket/serializers/ticket.py`
- `apps/inventory/services_import_export.py`
