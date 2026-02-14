# Payroll Models (`apps/payroll/models.py`)

## Scope
Defines payroll month headers, per-user lines, and allowance-gate decision history.

## Model Inventory
- `PayrollMonthly`: month-level state and aggregates.
- `PayrollMonthlyLine`: per-user computed payout row.
- `PayrollAllowanceGateDecision`: append-only manual decision log.

## Invariants and Constraints
- One `PayrollMonthly` per month.
- One `PayrollMonthlyLine` per (`payroll_monthly`, `user`).
- Decision events are append-only and time-indexed.

## Lifecycle Notes
- Header status transitions: `draft -> closed -> approved`.
- Decision events can occur only before approval.
- Header and line first-level actions now live in model methods:
  - `PayrollMonthly.assert_*`, `mark_closed`, `mark_approved`, `replace_lines`, `apply_allowance_release_delta`
  - `PayrollMonthlyLine.release_gated_allowance`
  - `PayrollAllowanceGateDecision.create_for_month`

## Operational Notes
- `rules_snapshot` freezes config inputs used during close.
- Query helpers are exposed through `PayrollMonthly.domain`.

## Related Code
- `apps/payroll/managers.py`
- `apps/payroll/services.py`
- `api/v1/payroll/views.py`
