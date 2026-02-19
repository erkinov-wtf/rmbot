# API v1 Inventory (`/inventory/`)

## Scope
Documents inventory resources:
- `Inventory` (group/place container)
- `InventoryItem`
- `InventoryItemCategory`
- `InventoryItemPart`

## Access Model
- Read (`GET` list/detail): any authenticated user.
- Write (`POST/PUT/PATCH/DELETE`): roles `super_admin`, `ops_manager`, `master`.

## Endpoint Reference

### Inventories
- `GET /api/v1/inventory/`
- `POST /api/v1/inventory/`
- `GET /api/v1/inventory/{id}/`
- `PUT/PATCH /api/v1/inventory/{id}/`
- `DELETE /api/v1/inventory/{id}/`

### Inventory items
- `GET /api/v1/inventory/items/`
- `POST /api/v1/inventory/items/`
- `GET /api/v1/inventory/items/{id}/`
- `PUT/PATCH /api/v1/inventory/items/{id}/`
- `DELETE /api/v1/inventory/items/{id}/`

### Inventory workbook import/export
- `GET /api/v1/inventory/export/` (download XLSX workbook)
- `POST /api/v1/inventory/import/` (upload XLSX workbook)

Workbook contract:
- Two required sheets: `Categories` and `Inventory Items`.
- `Categories` sheet is category + part oriented (`category_name`, `part_name`).
- `Inventory Items` sheet carries inventory-item fields (`serial_number`, `name`, `inventory_name`, `category_name`, `status`, `is_active`, `category_parts`).

List filters:
- `q` (serial lookup, min 2 chars, suggestion-style matching)
- `serial_number` (exact normalized match)
- `inventory`
- `category`
- `status`
- `is_active`
- `has_active_ticket`
- `created_from` / `created_to` (`YYYY-MM-DD`)
- `updated_from` / `updated_to` (`YYYY-MM-DD`)
- `ordering` (`created_at`, `-created_at`, `updated_at`, `-updated_at`, `serial_number`, `-serial_number`, `status`, `-status`)

Create/update notes:
- `serial_number` is normalized (trimmed/uppercased) and must stay unique.
- `name`, `inventory`, and `category` default when omitted during create.
- `parts` is read-only on item payloads; manage ownership through `/inventory/parts/` endpoints.

### Item categories
- `GET /api/v1/inventory/categories/`
- `POST /api/v1/inventory/categories/`
- `GET /api/v1/inventory/categories/{id}/`
- `PUT/PATCH /api/v1/inventory/categories/{id}/`
- `DELETE /api/v1/inventory/categories/{id}/`

Delete behavior notes:
- Category delete is rejected (`400`) when at least one active inventory item is assigned to that category.
- When no active items are assigned, category-level parts are soft-deleted first, then the category is soft-deleted.

### Item parts
- `GET /api/v1/inventory/parts/`
- `POST /api/v1/inventory/parts/`
- `GET /api/v1/inventory/parts/{id}/`
- `PUT/PATCH /api/v1/inventory/parts/{id}/`
- `DELETE /api/v1/inventory/parts/{id}/`

Create/update notes:
- `category` is required for category-level parts.
- `inventory_item` API writes are ignored (parts are normalized to category-level entities).
- Same `name` may be reused across different categories, but not duplicated within one category.

## Validation and Failure Modes
- Invalid/duplicate `serial_number` -> `400`.
- Import rejects files that are not `.xlsx` or workbook payloads missing required sheets/headers -> `400`.
- Too-short/invalid `q` or invalid filter values -> `400`.
- Unauthorized write role -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Archived inventory-item conflicts are handled in ticket intake (restore-required behavior).
- Ticket intake uses serial-number suggestions from the shared inventory item service.
- Workbook import is upsert-only and atomic (all-or-nothing on validation failure).

## Related Code
- `api/v1/inventory/urls.py`
- `api/v1/inventory/views.py`
- `api/v1/inventory/filters.py`
- `api/v1/inventory/serializers.py`
- `apps/inventory/models.py`
