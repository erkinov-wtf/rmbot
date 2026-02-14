# Ticket Work Session Service (`apps/ticket/services_work_session.py`)

## Scope
Controls work session timer lifecycle per ticket/technician.

## Execution Flows
- `start_work_session`
- `pause_work_session`
- `resume_work_session`
- `stop_work_session`
- transition history fetch (`get_ticket_work_session_history`)

## Invariants and Contracts
- Only assigned technician may control session.
- At most one open session per ticket.
- At most one open session per technician.
- Session transitions respect state order (`RUNNING <-> PAUSED -> STOPPED`).

## Side Effects
- Writes `WorkSession` and `WorkSessionTransition` rows.
- Recomputes `active_seconds` from transition history for consistency.
- May auto-start ticket workflow when beginning session from assign/rework states.

## Failure Modes
- No active session found for pause/resume/stop.
- Invalid state transitions.
- Ownership mismatch.

## Operational Notes
- Transition-history recomputation avoids timer drift from partial updates.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/services_workflow.py`
