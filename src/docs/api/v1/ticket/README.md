# API v1 Tickets (`/tickets/`)

## Scope
Documents ticket intake, workflow transitions, QC outcomes, and work-session timer endpoints.

## Access Model
- Authentication required for all endpoints.
- Role matrix:
  - Create: `master`, `super_admin`
  - Assign: `super_admin`, `ops_manager`, `master`
  - Workflow work actions: `technician`, `super_admin`
  - QC actions: `qc_inspector`, `super_admin`

## Endpoint Reference

### Ticket read/create
- `GET /api/v1/tickets/`: list tickets with relational context.
- `POST /api/v1/tickets/create/`: create intake ticket, approve SRT metadata, and append initial transition.
- `GET /api/v1/tickets/{id}/`: retrieve ticket detail.

### Workflow actions
- `POST /api/v1/tickets/{id}/assign/`: assign technician.
- `POST /api/v1/tickets/{id}/start/`: move into `IN_PROGRESS` and auto-start a running work session for the assigned technician.
- `POST /api/v1/tickets/{id}/to-waiting-qc/`: move to `WAITING_QC` only after the active work session is explicitly stopped.
- `POST /api/v1/tickets/{id}/qc-pass/`: finalize `DONE`, set inventory item ready, append XP entries.
- `POST /api/v1/tickets/{id}/qc-fail/`: move to `REWORK`.
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
  - checklist minimum item count
  - unknown serial number requires explicit confirm + reason to create inventory item
  - archived inventory item serial requires restore path, not implicit recreate
- Invalid state transitions/session actions -> `400`.
- Moving to QC while latest work session is not `STOPPED` -> `400`.
- Unauthorized role for action -> `403`.
- Missing/invalid JWT -> `401`.

## Operational Notes
- Ticket transitions and work-session history are append-only audit streams.
- `qc-pass` has cross-domain side effects (inventory-item state + XP ledger).
- Work-session active seconds are derived from transition history, not mutable counters only.

## Related Code
- `api/v1/ticket/urls.py`
- `api/v1/ticket/views/`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `apps/ticket/services_analytics.py`
