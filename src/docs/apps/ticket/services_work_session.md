# Ticket Work Session Service (`apps/ticket/services_work_session.py`)

## Scope
Orchestrates work-session lifecycle while delegating transition/state logic to `WorkSession` model methods.

## Execution Flows
- `pause_work_session`
- `resume_work_session`
- `stop_work_session`
- transition history fetch (`get_ticket_work_session_history`)

## Invariants and Contracts
- Only assigned technician may control session.
- At most one open session per ticket.
- At most one open session per technician.
- Session transitions respect state order (`RUNNING <-> PAUSED -> STOPPED`).
- Daily pause budget is enforced per technician from active rules config (`work_session.daily_pause_limit_minutes`).
- Pause budget resets on local-day boundaries from rules timezone (`work_session.timezone`).

## Side Effects
- Writes `WorkSession` and `WorkSessionTransition` rows via model methods.
- Recomputes `active_seconds` from transition history for consistency (`WorkSession.recalculate_active_seconds`).
- Auto-resumes paused sessions when daily pause budget is exhausted (manual flow guard + periodic Celery task).

## Failure Modes
- No active session found for pause/resume/stop.
- Invalid state transitions.
- Ownership mismatch.

## Operational Notes
- Open-session retrieval uses manager helpers (`WorkSession.domain`) to avoid duplicated query logic.
- Transition-history recomputation avoids timer drift from partial updates.
- Pause usage is calculated from persisted pause/resume/stop transition overlap within the current business day window.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/ticket/services_workflow.py`
