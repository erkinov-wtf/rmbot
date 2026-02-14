# Core Models and Deletion Semantics

## Scope
Documents shared model primitives used for timestamps, soft-deletion, and append-only audit safety.

## Base Model Layers
- `TimestampedModel`: common `created_at` / `updated_at`.
- `SoftDeleteModel`: `deleted_at` marker with soft-delete/restore API.
- `AppendOnlyModel`: immutable audit rows (no update/delete after insert).

## Invariants and Contracts
- Append-only entities reject:
  - queryset `update()` / `delete()`
  - instance updates via non-create `save()`
- Soft-deletable entities expose:
  - `objects` (active rows only)
  - `all_objects` (including deleted rows)
- Restore/hard-delete operations are explicit and intentional.

## Execution Flows

### Soft-delete cascade flow
1. `SoftDeleteModel.delete()` executes `_perform_on_delete()`.
2. CASCADE handlers are temporarily redirected to `SOFT_DELETE_CASCADE`.
3. ORM collector traverses relations; soft-deletable related rows are marked deleted.
4. Field-update cascades (`SET_NULL`, etc.) still apply through collector update phase.
5. Original CASCADE handlers are restored in `finally`.

### Append-only write flow
1. First insert is allowed.
2. Any subsequent mutation/delete path raises `ValidationError`.

## Failure Modes
- Mutating append-only rows raises validation exceptions.
- Attempted soft-delete cascades across unsupported assumptions can surface collector-level errors.

## Operational Notes
- Use `objects` in active business logic.
- Use `all_objects` in reconciliation/revival/admin repair flows.
- Append-only models are preferred for audit logs and payout/decision trails.

## Related Code
- `core/models.py`
- `core/managers.py`
- `core/utils/deletion.py`
