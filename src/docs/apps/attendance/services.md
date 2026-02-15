# Attendance Services (`apps/attendance/services.py`)

## Scope
Implements attendance check-in/check-out and punctuality XP posting with rules-driven time logic.
API callers are privileged managers who pass a technician user ID to record attendance on behalf of technicians.

## Execution Flows
- Resolve attendance rules (`_attendance_rules`).
- Resolve business date (`_business_date`).
- Resolve punctuality label (`resolve_punctuality_status`) as `early` / `on_time` / `late`.
- Filtered day list read (`list_today_records`) by date, technician, and punctuality label.
- Check-in orchestration (`check_in`) with model-level `mark_check_in` + XP append.
- Check-out orchestration (`check_out`) with model-level `mark_check_out`.

## Invariants and Contracts
- One attendance record per user/work-date.
- Check-in can happen once per business date.
- Check-out requires prior check-in and can happen once.

## Side Effects
- Writes attendance row and timestamps.
- Appends `attendance_punctuality` XP entry with deterministic reference key.

## Failure Modes
- Duplicate check-in.
- Check-out before check-in.
- Duplicate check-out.
- Invalid/partial rules values falling back to defaults.

## Operational Notes
- Business date and punctuality bucket use rules-configured timezone and cutoffs.
- Operations are transactional.

## Related Code
- `apps/attendance/models.py`
- `apps/attendance/managers.py`
- `apps/gamification/services.py`
- `apps/rules/services.py`
