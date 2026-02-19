# Inventory Import/Export Service (`apps/inventory/services_import_export.py`)

## Scope
Builds and parses inventory XLSX workbooks for bulk transfer of categories, parts, and inventory items.

## Execution Flows
- `export_workbook_bytes`: creates a 2-sheet workbook (`Categories`, `Inventory Items`) with full current inventory data.
- `import_workbook_bytes`: validates workbook shape and upserts categories, parts, and items from uploaded workbook rows.

## Invariants and Contracts
- Required sheets: `Categories`, `Inventory Items`.
- Required headers:
  - Categories: `category_name`, `part_name`
  - Inventory Items: `serial_number`, `name`, `inventory_name`, `category_name`, `status`, `is_active`, `category_parts`
- Import is upsert-only:
  - Categories by `name` (case-insensitive lookup).
  - Parts by `(category, name)` (case-insensitive lookup).
  - Items by `serial_number` (normalized, case-insensitive lookup).
- Soft-deleted entities are restored on upsert.

## Side Effects
- Inserts/updates `Inventory`, `InventoryItemCategory`, `InventoryItemPart`, and `InventoryItem` rows.
- Restores soft-deleted rows when matched by upsert identity.

## Failure Modes
- Missing required workbook sheet.
- Missing required headers in any required sheet.
- Missing required values (`category_name`, `serial_number`, etc.) in row payloads.
- Invalid `status` or boolean-like values (`is_active`).

## Operational Notes
- Import is wrapped in a single DB transaction (atomic all-or-nothing behavior).
- Export/import workbook excludes timestamp columns to keep file payload concise for operational bulk updates.

## Related Code
- `api/v1/inventory/views.py`
- `api/v1/inventory/urls.py`
- `apps/inventory/models.py`
- `apps/inventory/services.py`
