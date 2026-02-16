# Ticket Workflow Service (`apps/ticket/services_workflow.py`)

## Scope
Orchestrates core ticket transitions while delegating state mutation rules to model methods.

## Execution Flows
- `assign_ticket`
- `approve_ticket_review`
- `start_ticket`
- `move_ticket_to_waiting_qc`
- `qc_pass_ticket`
- `qc_fail_ticket`
- transition logging helper (`log_ticket_transition`)

## Invariants and Contracts
- Validation/state mutation ownership lives in `Ticket` model methods.
- Service remains responsible for cross-aggregate orchestration (inventory-item status + XP side effects).
- Assignment is blocked until ticket admin-review metadata (`approved_by`, `approved_at`) is present.
- Admin review approval is explicit via `approve_ticket_review`; manual metrics are no longer review-coupled.

## Side Effects
- Writes `TicketTransition` rows for each workflow action.
- Updates inventory-item status (`IN_SERVICE` on start, `READY` on QC pass).
- Starts a `WorkSession` automatically when `start_ticket` succeeds.
- Appends technician ticket XP entries on `qc-pass` (base + optional first-pass bonus).
- Appends QC inspector XP entries on every QC status update (`qc-pass` and `qc-fail`), using rules-config amount.
- Triggers user-facing Telegram notifications for assignment/start/waiting-QC/QC pass/QC fail via shared core notification service.
- Assignment and QC-fail notifications include technician inline action buttons resolved from `TechnicianTicketActionService`.

## Failure Modes
- Invalid source state for requested action.
- Technician mismatch or missing assignment.
- `start_ticket` is blocked while technician has any open work session (`RUNNING`/`PAUSED`) on another ticket.
- `move_ticket_to_waiting_qc` is blocked until the latest ticket session for that technician is `STOPPED`.

## Operational Notes
- XP formula inputs come from active rules (`ticket_xp` section).
- First-pass bonus eligibility requires both:
  - no prior `qc-fail` transition for the ticket
  - total accumulated work-session active time `<= ticket.total_duration` (planned minutes)
- Admin manual-metrics updates only affect metrics (`flag_color`, `xp_amount`, `is_manual`).
- Notification dispatch is deferred to transaction commit and is best-effort (non-blocking).

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/gamification/services.py`
- `apps/rules/services.py`
- `core/services/notifications.py`
