# API v1 Payroll (`/payroll/`)

## Scope
Documents monthly payroll snapshot lifecycle endpoints, including SLA-driven allowance gate decisions.

## Access Model
- Authentication required.
- Roles: `super_admin`, `ops_manager`.
- Path token `month` format: `YYYY-MM`.

## Endpoint Reference

### `GET /api/v1/payroll/{month}/`
- Returns payroll snapshot for target month.

### `POST /api/v1/payroll/{month}/close/`
- Computes payroll month from active rules and persisted ledger state.
- Stores immutable month snapshot fields (XP aggregates, payout components, rules/SLA snapshots).
- Applies allowance-gate policy at close time.

### `POST /api/v1/payroll/{month}/approve/`
- Marks closed month as approved for payout lifecycle.

### `POST /api/v1/payroll/{month}/allowance-gate/decision/`
- Records explicit Ops decision:
  - `keep_gated`
  - `release_allowances`
- `release_allowances` reapplies gated amounts and recalculates month totals.

## Validation and Failure Modes
- Invalid `month` token -> `400`.
- Missing month snapshot on detail/approve/decision -> `404`.
- Invalid lifecycle transition (e.g., approve before close, repeated actions) -> `400`.
- Invalid decision payload -> `400`.
- Unauthorized role -> `403`.

## Operational Notes
- Payroll month data is snapshot-driven; rules updates after close do not retroactively mutate closed snapshot.
- Allowance gate decisions are append-only auditable events.

## Related Code
- `api/v1/payroll/urls.py`
- `api/v1/payroll/views.py`
- `apps/payroll/services.py`
- `apps/payroll/models.py`
