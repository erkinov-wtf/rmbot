# Rules Services (`apps/rules/services.py`)

## Scope
Provides default rules, strict normalization, versioned update/rollback orchestration, and active-config caching.

## Execution Flows
- Bootstrap state/version if absent (`ensure_rules_state`).
- Validate and normalize input config (`validate_and_normalize_rules_config`).
- Update config with diff + new immutable version (`update_rules_config`).
- Roll back to target version by creating new rollback version (`rollback_rules_config`).
- Read active state/config with cache support.

## Service vs Domain Responsibilities
- Service-owned:
  - schema/range normalization,
  - checksum + diff generation,
  - cache invalidation/write-through.
- Model/manager-owned:
  - singleton row lock/read,
  - version row creation,
  - state activation persistence.

## Invariants and Contracts
- Unknown top-level keys are rejected.
- Progression thresholds are non-decreasing; L1 threshold fixed at zero.
- `work_session.daily_pause_limit_minutes` must be a non-negative integer.
- `attendance.timezone` and `work_session.timezone` must be non-empty strings.
- Updates/rollbacks always create new immutable version rows.
- Cache key rotates on each activation change.

## Failure Modes
- Invalid config payload shape/range.
- No-op updates rejected.
- Rollback target missing or already active.

## Operational Notes
- Consumers should read/update rules only via service methods.

## Related Code
- `apps/rules/models.py`
- `apps/rules/managers.py`
- `api/v1/rules/views.py`
- `apps/*/services.py` consumers
