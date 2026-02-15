# Ticket Managers (`apps/ticket/managers.py`)

## Scope
Defines domain query helpers for ticket/work-session lifecycle and transitions.

## Manager Inventory
- `TicketQuerySet` + `TicketDomainManager`
- `WorkSessionQuerySet` + `WorkSessionDomainManager`
- `TicketTransitionDomainManager`
- `WorkSessionTransitionDomainManager`

## Execution Notes
- `Ticket.domain` centralizes active-workflow and technician-state lookups plus backlog pressure count (`backlog_black_plus_count`, currently mapped to red-severity backlog volume).
- `WorkSession.domain` provides both open-session retrieval and latest-session lookup per ticket/technician for workflow gating.
- Transition managers provide read helpers:
  - QC-fail existence lookup (`has_qc_fail_for_ticket`)
  - ticket-scoped work-session transition history (`history_for_ticket`)

## Invariants and Contracts
- Ticket/work-session managers apply alive-only filtering (`deleted_at IS NULL`).

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
