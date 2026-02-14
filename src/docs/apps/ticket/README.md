# Ticket App Docs

## Scope
Covers ticket lifecycle, work sessions, stockout detection, SLA automation, escalation delivery, and analytics.

## Navigation
- `docs/apps/ticket/models.md`
- `docs/apps/ticket/managers.md`
- `docs/apps/ticket/services_workflow.md`
- `docs/apps/ticket/services_work_session.md`
- `docs/apps/ticket/services_analytics.md`
- `docs/apps/ticket/services_stockout.md`
- `docs/apps/ticket/services_sla.md`
- `docs/apps/ticket/services_sla_escalation.md`

## Maintenance Rules
- Update docs whenever ticket state machine, session rules, SLA logic, or escalation channel behavior changes.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/ticket/services_*.py`
- `apps/ticket/tasks.py`
- `api/v1/ticket/`
