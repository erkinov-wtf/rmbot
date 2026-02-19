# Generate Mock Data Command (`core/management/commands/generate_mock_data.py`)

## Scope
Generates a large historical mock dataset for load-style testing of inventory, parts, tickets, transitions, and XP analytics while keeping generated mock users capped to 10.

## Command Interface
- Run: `python src/manage.py generate_mock_data`
- Main sizing flags:
  - `--users` (hard-capped to 10)
  - `--items`
  - `--tickets`
  - `--parts-per-item`
  - `--categories`
- History/randomization flags:
  - `--lookback-days` (uniform time spread window)
  - `--seed` (deterministic random sequence)
  - `--run-tag` (namespace for generated names/references)
- Bulk insert tuning:
  - `--batch-size`

## Data Generation Model
- Creates/reuses up to 10 deterministic mock users with role coverage (`super_admin`, `ops_manager`, `master`, `technician`, `qc_inspector`).
- Creates one run-scoped inventory, multiple categories, many items, and per-item parts.
- Creates many tickets with approximately uniform random status distribution and realistic lifecycle timestamps.
- Adds ticket transitions (`created`, `assigned`, `started`, `to_waiting_qc`, `qc_fail`, `qc_pass`) in chronological order.
- Adds XP transaction rows for ticket base XP, first-pass bonus, and QC status-update events.
- Adds ticket part specs sampled from each ticket’s inventory item parts.

## Invariants and Contracts
- User generation enforces a hard cap of 10 mock users, even when `--users` is higher.
- Historical timestamps are sampled uniformly across the requested lookback range.
- Active-ticket uniqueness per inventory item is preserved (fallback to `done` when needed).
- Run-tag collisions are blocked when serial/category namespaces already exist.

## Failure Modes
- Invalid non-positive numeric arguments raise command errors.
- Invalid/empty `--run-tag` after normalization raises command errors.
- Existing serial/category namespace for the same run-tag aborts generation to avoid collisions.

## Operational Notes
- Command writes directly via model `bulk_create` for speed and does not call workflow services.
- Because workflow services are bypassed, user-facing Telegram notifications are not emitted by this command.
- Recommended for local/staging synthetic data seeding before analytics or queue load checks.

## Related Code
- `core/management/commands/generate_mock_data.py`
- `apps/inventory/models.py`
- `apps/ticket/models.py`
- `apps/gamification/models.py`
