# Rules Services (`apps/rules/services.py`)

## Scope
Provides default rules, strict normalization, versioned updates/rollback, and active-config caching.

## Execution Flows
- Bootstrap state/version if absent (`ensure_rules_state`).
- Validate and normalize input config (`validate_and_normalize_rules_config`).
- Update config with diff + new version (`update_rules_config`).
- Roll back to target version by creating new rollback version (`rollback_rules_config`).
- Read active state/config with cache support.

## Invariants and Contracts
- Unknown top-level keys are rejected.
- Numeric/range and shape checks enforced across all rule domains.
- Progression thresholds are non-decreasing; L1 threshold fixed at zero.
- Updates/rollbacks always create new immutable version rows.
- Cache key rotates on each activation change.

## Side Effects
- Writes version history and active-state pointer.
- Invalidates old cache key and stores new cached config snapshot.

## Failure Modes
- Invalid schema/range in config payload.
- No-op updates rejected.
- Rollback target missing or already active.

## Operational Notes
- SLA escalation routing is validated as part of rules schema.
- Consumers should read rules only via service methods.

## Related Code
- `apps/rules/models.py`
- `api/v1/rules/views.py`
- `apps/*/services.py` consumers
