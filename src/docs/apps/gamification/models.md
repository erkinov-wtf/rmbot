# Gamification Models (`apps/gamification/models.py`)

## Scope
Defines append-only XP and progression event records.

## Model Inventory
- `XPLedger`: immutable XP entries with unique reference key.
- `WeeklyLevelEvaluation`: immutable weekly level decision snapshot.
- `LevelUpCouponEvent`: immutable coupon issuance event.

## Invariants and Constraints
- `XPLedger.reference` unique (idempotency guard).
- `WeeklyLevelEvaluation` unique per (`week_start`, `user`).
- `LevelUpCouponEvent.reference` unique.

## Lifecycle Notes
- Records are append-only; correction should be represented by compensating entries/events.
- `XPLedger.objects` now uses a custom append-only manager with idempotent writer helper (`append_entry`).

## Operational Notes
- These tables are the audit source for XP/progression calculations.

## Related Code
- `apps/gamification/services.py`
- `apps/gamification/tasks.py`
- `api/v1/gamification/views.py`
