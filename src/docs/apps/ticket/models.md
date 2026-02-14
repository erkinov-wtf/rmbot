# Ticket Models (`apps/ticket/models.py`)

## Scope
Defines workflow, work-session, stockout, and SLA automation persistence for operations and payroll analytics.

## Model Inventory
- `Ticket`, `TicketTransition`
- `WorkSession`, `WorkSessionTransition`
- `StockoutIncident`
- `SLAAutomationEvent`, `SLAAutomationDeliveryAttempt`

## Domain Hooks
- `Ticket.domain`, `WorkSession.domain`, `TicketTransition.domain`, `WorkSessionTransition.domain`
- `StockoutIncident.domain`
- `SLAAutomationEvent.domain`
- `SLAAutomationDeliveryAttempt.domain`

## Lifecycle Notes
- Ticket/session first-level transitions:
  - `Ticket.assign_to_technician`, `start_progress`, `move_to_waiting_qc`, `mark_qc_pass`, `mark_qc_fail`, `add_transition`
  - `WorkSession.start_for_ticket`, `pause`, `resume`, `stop`, `add_transition`, `recalculate_active_seconds`
- Stockout first-level actions:
  - `StockoutIncident.start_incident`, `resolve`, `overlap_minutes`
- SLA automation first-level actions:
  - `SLAAutomationEvent.create_event`, `evaluated_at_or_created`, `is_repeat`
  - `SLAAutomationDeliveryAttempt.create_from_delivery_response`

## Invariants and Constraints
- One active ticket per bike.
- One `IN_PROGRESS` ticket per technician.
- One open work session per ticket and per technician.
- Transition/event/attempt entities remain append-only where designed.

## Operational Notes
- Service classes orchestrate rule evaluation/delivery flows while model methods own first-level state transitions and append-only row creation.

## Related Code
- `apps/ticket/managers.py`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `apps/ticket/services_sla.py`
- `apps/ticket/services_sla_escalation.py`
- `apps/ticket/services_stockout.py`
