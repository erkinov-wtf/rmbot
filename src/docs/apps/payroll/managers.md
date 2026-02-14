# Payroll Managers (`apps/payroll/managers.py`)

## Scope
Provides reusable payroll-month query helpers for related-object loading and lock-safe month retrieval.

## Manager Inventory
- `PayrollMonthlyQuerySet`: `with_related`, `for_month`.
- `PayrollMonthlyDomainManager`: month lookup helpers with and without `select_for_update`.

## Execution Notes
- `get_or_create_for_month_for_update` is used by close workflow to keep month header creation lock-safe.
- `get_for_month_for_update` is used by approval and allowance decision flows.
- `with_related` keeps API serialization queries consistent across service entry points.

## Invariants and Contracts
- Query helpers do not mutate state.
- Locking behavior is explicit and only used in write workflows.

## Related Code
- `apps/payroll/models.py`
- `apps/payroll/services.py`
- `api/v1/payroll/views.py`
