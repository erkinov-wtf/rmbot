# Ticket Models (`apps/ticket/models.py`)

## Scope
Defines workflow and work-session persistence for operational execution and analytics.

## Model Inventory
- `Ticket`, `TicketPartSpec`, `TicketTransition`
- `WorkSession`, `WorkSessionTransition`

## Domain Hooks
- `Ticket.domain`, `WorkSession.domain`, `TicketTransition.domain`, `WorkSessionTransition.domain`

## Lifecycle Notes
- Ticket/session first-level transitions:
  - `Ticket.assign_to_technician`, `start_progress`, `move_to_waiting_qc`, `mark_qc_pass`, `mark_qc_fail`, `add_transition`
  - ticket metrics helpers: `flag_color_from_minutes`, `apply_auto_metrics`, `apply_manual_metrics`
  - `WorkSession.start_for_ticket`, `pause`, `resume`, `stop`, `add_transition`, `recalculate_active_seconds`

## Invariants and Constraints
- One active ticket per inventory item.
- No hard cap on `IN_PROGRESS` ticket rows per technician; start concurrency is enforced by work-session guards.
- One active part-spec row per `(ticket, inventory_item_part)`.
- `TicketPartSpec.inventory_item_part` points to an item-owned inventory part (parts are not shared across inventory items).
- One open work session per ticket and per technician.
- Transition/event/attempt entities remain append-only where designed.

## Operational Notes
- Ticket default status is `UNDER_REVIEW`; it must be admin-reviewed (`approved_by` + `approved_at`) before assignment.
- Admin review can move `UNDER_REVIEW -> NEW`, after which assignment transitions the ticket into active workflow.
- Ticket metrics (`total_duration`, `flag_minutes`, `flag_color`, `xp_amount`) are computed from ticket part specs unless manually overridden.
- Ticket completion timestamp is stored in `finished_at`.
- Ticket and part-spec colors are constrained to `green`, `yellow`, and `red`.
- Work-session pause/resume transitions may include metadata for pause-budget enforcement (remaining budget / auto-resume reason).
- Service classes orchestrate rule evaluation/delivery flows while model methods own first-level state transitions and append-only row creation.

## Related Code
- `apps/ticket/managers.py`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
