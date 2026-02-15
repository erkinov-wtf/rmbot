# Ticket Workflow Service (`apps/ticket/services_workflow.py`)

## Scope
Orchestrates core ticket transitions while delegating state mutation rules to model methods.

## Execution Flows
- `assign_ticket`
- `start_ticket`
- `move_ticket_to_waiting_qc`
- `qc_pass_ticket`
- `qc_fail_ticket`
- transition logging helper (`log_ticket_transition`)

## Invariants and Contracts
- Validation/state mutation ownership lives in `Ticket` model methods.
- Service remains responsible for cross-aggregate orchestration (bike status + XP side effects).

## Side Effects
- Writes `TicketTransition` rows for each workflow action.
- Updates bike status (`IN_SERVICE` on start, `READY` on QC pass).
- Starts a `WorkSession` automatically when `start_ticket` succeeds.
- Appends XP ledger base and optional first-pass bonus entries.

## Failure Modes
- Invalid source state for requested action.
- Technician mismatch or missing assignment.
- Unique in-progress technician constraint violations surfaced as errors.
- `move_ticket_to_waiting_qc` is blocked until the latest ticket session for that technician is `STOPPED`.

## Operational Notes
- XP formula inputs come from active rules (`ticket_xp` section).

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/gamification/services.py`
- `apps/rules/services.py`
