# Core API Runtime Contract

## Scope
Defines shared DRF response envelopes, pagination shape, exception normalization, and role-based permission helpers.

## Response Envelope Contract
- `CustomResponseMixin.finalize_response()` wraps unstructured API responses.
- Success shape: `{ "success": true, "message": "...", "data": ... }`.
- Error shape: `{ "success": false, "message": "...", "error": ... }`.
- Pre-structured payloads are passed through without double wrapping.

## Pagination Contract
- `PaginatedListMixin` + `CustomPagination` emit:
  - `results`
  - `total_count`
  - `page`
  - `page_count`
  - `per_page`
- Empty list responses still preserve the same structured payload.

## Exception Normalization
- Global handler: `core.api.exceptions.custom_exception_handler`.
- Validation trees are flattened into stable client-facing message strings.
- Envelope remains consistent with machine-readable error metadata.

## Access Control Contract
- `HasRole.as_any(...)` dynamically composes role-based permission classes.
- Role checks evaluate `request.user.roles` by slug.

## Failure Modes
- Raw DRF generic views can bypass envelope mixins when not using core base views.
- Inconsistent manual responses can break client assumptions if contract is ignored.

## Operational Notes
- Prefer `core.api.views` base classes/viewsets for new endpoints.
- Use explicit opt-outs only when raw responses are required by design.

## Related Code
- `core/api/views.py`
- `core/api/exceptions.py`
- `core/api/permissions.py`
- `core/utils/pagination.py`
