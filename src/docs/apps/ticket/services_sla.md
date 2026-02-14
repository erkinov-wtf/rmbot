# SLA Automation Service (`apps/ticket/services_sla.py`)

## Scope
Evaluates SLA thresholds and emits trigger/resolve events for operational automation.

## Execution Flows
- Load automation thresholds from active rules.
- Collect current metrics (stockout duration, backlog pressure, QC rate).
- Evaluate each rule key and apply cooldown policy.
- Emit `SLAAutomationEvent` rows for trigger/reminder/resolve outcomes.

## Invariants and Contracts
- Event generation respects cooldown for repeated triggers.
- Resolve events are emitted only when prior state was triggered.

## Side Effects
- Writes append-only SLA automation event rows.

## Failure Modes
- Disabled automation returns metrics with no events.
- Missing/invalid rules values fall back to defaults.

## Operational Notes
- Created event IDs are consumed by escalation delivery task queue.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/services_analytics.py`
- `apps/ticket/tasks.py`
