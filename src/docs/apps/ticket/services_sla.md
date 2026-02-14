# SLA Automation Service (`apps/ticket/services_sla.py`)

## Scope
Evaluates SLA thresholds and emits trigger/resolve automation events for operational workflows.

## Execution Flows
- Load automation thresholds from active rules.
- Collect current metrics (stockout duration, backlog pressure, QC rate).
- Evaluate each rule key and apply cooldown policy.
- Emit `SLAAutomationEvent` rows for trigger/reminder/resolve outcomes.

## Service vs Domain Responsibilities
- Service-owned:
  - threshold evaluation logic,
  - cooldown orchestration,
  - result payload assembly.
- Model/manager-owned:
  - latest event reads per rule (`SLAAutomationEvent.domain.latest_for_rule`),
  - event creation (`SLAAutomationEvent.create_event`),
  - event timestamp extraction (`evaluated_at_or_created`),
  - backlog pressure query (`Ticket.domain.backlog_black_plus_count`),
  - active stockout lookup (`StockoutIncident.domain.latest_active`).

## Invariants and Contracts
- Event generation respects cooldown for repeated triggers.
- Resolve events are emitted only when prior state was `triggered`.

## Side Effects
- Writes append-only SLA automation event rows.

## Failure Modes
- Disabled automation returns metrics with no events.
- Missing/invalid rules values fall back to defaults.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/ticket/services_analytics.py`
- `apps/ticket/tasks.py`
