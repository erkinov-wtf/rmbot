# Attendance Managers (`apps/attendance/managers.py`)

## Scope
Provides reusable attendance retrieval helpers for business-date operations.

## Manager Inventory
- `AttendanceRecordQuerySet`: composable filters (`for_user`, `on_work_date`, `with_check_in`).
- `AttendanceRecordDomainManager`: alive-only manager with lookup/restore helpers.

## Execution Notes
- `for_user_on_date` resolves today's row lookup with soft-delete filtering.
- `get_or_restore_for_user_on_date` revives soft-deleted records before service writes.

## Invariants and Contracts
- Domain manager queryset always applies `deleted_at IS NULL`.
- Restore helper is the only manager path that intentionally touches `all_objects`.

## Related Code
- `apps/attendance/models.py`
- `apps/attendance/services.py`
- `apps/ticket/services_analytics.py`
