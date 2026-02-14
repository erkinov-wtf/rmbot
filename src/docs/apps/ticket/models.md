# Ticket Models (`apps/ticket/models.py`)

## Scope
Defines workflow, session, SLA, and stockout persistence for the service lifecycle.

## Model Inventory
- `Ticket`, `TicketTransition`
- `WorkSession`, `WorkSessionTransition`
- `StockoutIncident`
- `SLAAutomationEvent`, `SLAAutomationDeliveryAttempt`

## Invariants and Constraints
- One active ticket per bike.
- One `IN_PROGRESS` ticket per technician.
- One open work session per ticket and per technician.
- Transition/event attempt entities are append-only.

## Lifecycle Notes
- Ticket and session states transition through service-level state machines.
- SLA and delivery attempts accumulate as event history.

## Operational Notes
- These models power analytics, payroll gating, and operational audit feed.

## Related Code
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `apps/ticket/services_sla.py`
- `apps/ticket/services_sla_escalation.py`
