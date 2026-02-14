# Gamification Services (`apps/gamification/services.py`)

## Scope
Handles append-only XP posting and weekly progression evaluations.

## Execution Flows
- XP append orchestration (`append_xp_entry`) delegating idempotent writes to `XPLedger.objects.append_entry`.
- Weekly evaluation (`run_weekly_level_evaluation`) from XP aggregates.
- Level mapping (`map_raw_xp_to_level`) with monotonic threshold assumptions.
- Coupon issuance for level-up events.

## Invariants and Contracts
- XP entries are idempotent by unique reference.
- Weekly evaluation row is unique per user/week.
- User level never decreases during evaluation (`max(previous, mapped)`).

## Side Effects
- Appends ledger/evaluation/coupon rows.
- Updates `User.level` when level-up detected.

## Failure Modes
- Invalid week token format/non-Monday input.
- Missing actor user (when provided).
- Coupon duplicate integrity conflict (ignored).

## Operational Notes
- Week bounds use business timezone (`Asia/Tashkent`).
- Rules snapshot version/cache key is persisted with evaluations.

## Related Code
- `apps/gamification/models.py`
- `apps/rules/services.py`
- `apps/gamification/tasks.py`
