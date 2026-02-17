# Bot Permission Mapping (`bot/permissions.py`)

## Scope
Defines bot-side capability gates for ticket intake/review UI using the same role rules as DRF API ticket permission classes.

## Execution Flow
- `resolve_ticket_bot_permissions(user=...)` computes:
  - `can_create` from `TicketCreatePermission`
  - `can_review` from `TicketReviewPermission`
  - `can_assign` from `TicketAssignPermission`
  - `can_manual_metrics` from `TicketManualMetricsPermission`
- Derived flags:
  - `can_open_review_panel` enables the review queue surface.
  - `can_approve_and_assign` enables combined approve+assign action.

## Invariants and Contracts
- Permission evaluation is API-first: role semantics come from `api/v1/ticket/permissions.py`, not duplicated bot role lists.
- Inactive or missing users always resolve to all-false permission flags.
- Bot menu visibility and callback-level authorization must both read this permission set.

## Failure Modes
- If a role map changes in API permissions but bot docs/tests are not updated, button visibility may drift. Keep unit tests aligned with permission classes.

## Related Code
- `bot/permissions.py`
- `api/v1/ticket/permissions.py`
- `bot/routers/start/__init__.py`
- `bot/routers/ticket_admin/__init__.py`
