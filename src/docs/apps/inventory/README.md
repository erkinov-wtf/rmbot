# Inventory App Docs

## Scope
Covers inventory entities (`Inventory`, `InventoryItem`, category, item-owned parts), serial-number normalization/lookup/suggestion logic, and list-filter query primitives used by inventory APIs.

## Navigation
- `docs/apps/inventory/models.md`
- `docs/apps/inventory/managers.md`
- `docs/apps/inventory/services.md`

## Maintenance Rules
- Update docs when inventory model relations, serial-number validation/suggestion behavior, or inventory-item list filtering behavior changes.

## Related Code
- `apps/inventory/models.py`
- `apps/inventory/managers.py`
- `apps/inventory/services.py`
- `api/v1/inventory/`
