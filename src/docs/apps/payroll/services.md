# Payroll Services (`apps/payroll/services.py`)

## Scope
Implements payroll month close, allowance decision, and approval orchestration using model-level state APIs.

## Execution Flows
- Parse month + compute month bounds.
- Close month: aggregate XP, apply caps/allowances, persist lines and totals.
- Apply allowance decision: keep gated or release gated allowances.
- Approve month: transition to final approved state.

## Invariants and Contracts
- Month token must be `YYYY-MM`.
- State transitions enforce `draft -> closed -> approved` ordering.
- Allowance decisions cannot mutate approved months.
- Releasing allowances requires at least one gated line.

## Side Effects
- Rebuilds month lines on close.
- Stores rules and SLA snapshots on payroll header.
- Writes append-only allowance decision rows.
- Updates aggregate totals when allowances are released.

## Failure Modes
- Invalid month token.
- Closing already closed/approved month.
- Approving non-closed month.
- Invalid decision value or no releasable gated lines.

## Operational Notes
- Allowance gate thresholds derive from active rules SLA section.
- Snapshot storage makes historical payroll reproducible.
- Service delegates status mutation and line mutation to `PayrollMonthly` / `PayrollMonthlyLine` methods.

## Related Code
- `apps/payroll/models.py`
- `apps/payroll/managers.py`
- `apps/rules/services.py`
- `apps/ticket/services_stockout.py`
- `api/v1/payroll/views.py`
