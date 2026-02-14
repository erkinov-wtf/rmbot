# Ticket Managers (`apps/ticket/managers.py`)

## Scope
Defines domain query helpers for ticket/work-session lifecycle, stockout tracking, and SLA automation delivery history.

## Manager Inventory
- `TicketQuerySet` + `TicketDomainManager`
- `StockoutIncidentQuerySet` + `StockoutIncidentDomainManager`
- `SLAAutomationEventQuerySet` + `SLAAutomationEventDomainManager`
- `SLAAutomationDeliveryAttemptQuerySet` + `SLAAutomationDeliveryAttemptDomainManager`
- `WorkSessionQuerySet` + `WorkSessionDomainManager`
- `TicketTransitionDomainManager`
- `WorkSessionTransitionDomainManager`

## Execution Notes
- `Ticket.domain` centralizes active-workflow and technician-state lookups plus backlog pressure count (`backlog_black_plus_count`).
- `StockoutIncident.domain` centralizes active incident lookup (including `select_for_update`) and window-overlap selection.
- `SLAAutomationEvent.domain` centralizes latest-per-rule and id-based reads.
- `SLAAutomationDeliveryAttempt.domain` centralizes success-existence checks for idempotent delivery behavior.
- Transition managers provide read helpers:
  - QC-fail existence lookup (`has_qc_fail_for_ticket`)
  - ticket-scoped work-session transition history (`history_for_ticket`)

## Invariants and Contracts
- Ticket/work-session managers apply alive-only filtering (`deleted_at IS NULL`).
- SLA/stockout managers are read/query helpers; append-only and lifecycle writes are handled by model first-level actions.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `apps/ticket/services_sla.py`
- `apps/ticket/services_sla_escalation.py`
- `apps/ticket/services_stockout.py`
