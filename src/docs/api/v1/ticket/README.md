# API v1 Tickets (`/tickets/`)

## Scope
Documents ticket intake, workflow transitions, QC outcomes, and work-session timer endpoints.

## Access Model
- Authentication required for all endpoints.
- Role matrix:
  - Create: `master`, `super_admin`
  - Assign: `super_admin`, `ops_manager`
  - Workflow work actions: `technician`, `super_admin`
  - QC actions: `qc_inspector`, `super_admin`

## Endpoint Reference

### Ticket read/create
- `GET /api/v1/tickets/`: list tickets with relational context.
- `POST /api/v1/tickets/create/`: create intake ticket, compute metrics from part specs, and append initial transition.
- `GET /api/v1/tickets/{id}/`: retrieve ticket detail.

### Workflow actions
- `POST /api/v1/tickets/{id}/assign/`: assign technician (allowed only after admin review approval).
- `POST /api/v1/tickets/{id}/start/`: move into `IN_PROGRESS` and auto-start a running work session for the assigned technician.
- `POST /api/v1/tickets/{id}/to-waiting-qc/`: move to `WAITING_QC` only after the active work session is explicitly stopped.
- `POST /api/v1/tickets/{id}/qc-pass/`: finalize `DONE`, set inventory item ready, append technician base XP, checker status-update XP, and conditional first-pass bonus.
- `POST /api/v1/tickets/{id}/qc-fail/`: move to `REWORK` and append checker status-update XP.
- `POST /api/v1/tickets/{id}/manual-metrics/`: admin override for `flag_color`/`xp_amount`; also persists review approval metadata.
- `GET /api/v1/tickets/{id}/transitions/`: paginated list of append-only workflow transitions.

### Work-session actions
- `POST /api/v1/tickets/{id}/work-session/pause/`
- `POST /api/v1/tickets/{id}/work-session/resume/`
- `POST /api/v1/tickets/{id}/work-session/stop/`
- `GET /api/v1/tickets/{id}/work-session/history/` (paginated)

## Validation and Failure Modes
- Intake constraints:
  - one active ticket per inventory item
  - one `IN_PROGRESS` ticket per technician
  - unknown serial number requires explicit confirm + reason to create inventory item
  - archived inventory item serial requires restore path, not implicit recreate
- Ticket assignment requires prior admin review approval (`approved_by`, `approved_at`).
- Allowed ticket colors are `green`, `yellow`, `red` (including part-spec and manual-metrics inputs).
- Invalid state transitions/session actions -> `400`.
- Daily work-session pause budget is enforced per technician (`work_session.daily_pause_limit_minutes`); pause fails when exhausted.
- Paused sessions are auto-resumed when today's pause budget is consumed, and budget resets after local midnight (`work_session.timezone`).
- Moving to QC while latest work session is not `STOPPED` -> `400`.
- Unauthorized role for action -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Ticket transitions and work-session history are append-only audit streams.
- `qc-pass` has cross-domain side effects (inventory-item state + XP transactions).
- First-pass bonus is only awarded when there is no prior rework (`qc-fail`) and total active work time is within planned duration (`<= total_duration`).
- Work-session active seconds are derived from transition history, not mutable counters only.

## Related Code
- `api/v1/ticket/urls.py`
- `api/v1/ticket/views/`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `apps/ticket/services_analytics.py`
