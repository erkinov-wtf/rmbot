# Stockout Incident Service (`apps/ticket/services_stockout.py`)

## Scope
Detects and resolves stockout incidents using rules-defined business windows.

## Execution Flows
- Load stockout config (`_stockout_config`).
- Compute window context (`business_window_context`).
- Detect/start/resolve incidents (`detect_and_sync`).
- Aggregate overlap summaries (`stockout_window_summary`, `monthly_sla_snapshot`, `rolling_stockout_summary`).

## Service vs Domain Responsibilities
- Service-owned:
  - business window/calendar calculation,
  - decision branching (start/resolve/no-op),
  - SLA snapshot aggregation.
- Model/manager-owned:
  - active incident lock/read (`StockoutIncident.domain.latest_active_for_update`),
  - incident creation (`StockoutIncident.start_incident`),
  - incident resolution (`StockoutIncident.resolve`),
  - overlap minute calculation (`StockoutIncident.overlap_minutes`),
  - overlap window query (`StockoutIncident.domain.list_overlapping_window`).

## Invariants and Contracts
- Incidents open only when in business window and ready fleet count is zero.
- Incident resolution persists duration and ending ready count.
- Business calendar supports weekdays + holiday date overrides from rules.

## Side Effects
- Creates/updates `StockoutIncident` records.
- Provides SLA snapshot inputs for payroll and automation.

## Failure Modes
- Invalid rule values are sanitized to safe defaults.
- Out-of-window conditions do not trigger incidents.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/rules/services.py`
- `apps/ticket/tasks.py`
