# Ticket Analytics Service (`apps/ticket/services_analytics.py`)

## Scope
Builds fleet and team KPI aggregates for analytics endpoints.

## Execution Flows
- Fleet snapshot (`fleet_summary`): availability, backlog, SLA pressure, QC trend, stockout rollups.
- Team snapshot (`team_summary`): per-technician output and period totals.

## Invariants and Contracts
- Output payload keys remain stable for API consumers.
- Team metrics are bounded by requested day window.

## Side Effects
- Read-only service (no writes).

## Failure Modes
- No active technicians -> returns empty members with summary defaults.

## Operational Notes
- Uses stockout business-window context and incident summaries.
- Uses ticket transitions to infer first-pass QC rate.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/services_stockout.py`
- `api/v1/core/views/analytics.py`
