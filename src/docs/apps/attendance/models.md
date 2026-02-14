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

## Operational Notes
- Business date is timezone-aware and rules-driven at service layer.

## Related Code
- `apps/attendance/services.py`
- `api/v1/attendance/views.py`
