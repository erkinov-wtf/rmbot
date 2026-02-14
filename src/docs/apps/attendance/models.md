# Attendance Models (`apps/attendance/models.py`)

## Scope
Defines per-user daily attendance records.

## Model Inventory
- `AttendanceRecord`: work-date row containing check-in/check-out timestamps.

## Invariants and Constraints
- Unique attendance row per (`user`, `work_date`) (soft-delete aware).
- Indexed for fast day/user lookups.

## Lifecycle Notes
- Rows are created/updated by attendance service operations.
- Soft-deleted records can be revived during check-in flow.
- Timestamp mutations now use model-level methods:
  - `mark_check_in`
  - `mark_check_out`

## Operational Notes
- Business date is timezone-aware and rules-driven at service layer.
- Query access is centralized through `AttendanceRecord.domain`.

## Related Code
- `apps/attendance/services.py`
- `apps/attendance/managers.py`
- `api/v1/attendance/views.py`
