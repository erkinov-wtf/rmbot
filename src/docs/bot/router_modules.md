# Bot Router Modules

## Scope
Documents the class-based router module split used by `src/bot/routers/`.

## Module Inventory
- `bot/routers/start/__init__.py` composes onboarding/profile/XP routers.
- `bot/routers/start/access.py` owns onboarding FSM entrypoints and access-request form handlers.
- `bot/routers/start/profile.py` owns profile/help entrypoints.
- `bot/routers/start/xp.py` owns XP summary/history entrypoints and pagination callback.
- `bot/routers/start/common.py` provides shared onboarding state mixins and FSM states.
- `bot/routers/technician_tickets/__init__.py` composes technician entrypoint/callback routers.
- `bot/routers/technician_tickets/entry.py` owns technician queue entrypoint handlers.
- `bot/routers/technician_tickets/callbacks.py` owns technician queue/ticket callback handlers.
- `bot/routers/ticket_admin/__init__.py` composes create/review routers.
- `bot/routers/ticket_admin/create.py` composes ticket-create entrypoint/callback routers.
- `bot/routers/ticket_admin/create_entry.py` owns ticket-create entrypoint handlers.
- `bot/routers/ticket_admin/create_callbacks.py` owns ticket-create callback flow handlers.
- `bot/routers/ticket_admin/review.py` composes ticket-review entrypoint/callback routers.
- `bot/routers/ticket_admin/review_entry.py` owns ticket-review entrypoint handlers.
- `bot/routers/ticket_admin/review_callbacks.py` owns ticket-review callback flow handlers.
- `bot/routers/ticket_qc/__init__.py` composes QC entrypoint/callback routers.
- `bot/routers/ticket_qc/base.py` provides shared classmethod helpers for QC handlers.
- `bot/routers/ticket_qc/entry.py` owns QC queue entrypoint handlers.
- `bot/routers/ticket_qc/callbacks.py` owns QC queue/action callback handlers.

## Invariants and Contracts
- Router entrypoint modules and callback modules remain class-based only (`MessageHandler` / `CallbackQueryHandler`).
- Callback payload contracts stay stable (`xph`, `ttq`, `tt`, `tc`, `trq`, `tra`, `tqq`, `tqc`).
- Shared helpers for guard checks/state cleanup live on classmethods in base handler classes/mixins.

## Operational Notes
- Feature router package `__init__.py` files are composition-only modules.
- The unit guard `tests/unit/bot/test_handler_registration.py` enforces class-based handler registration across the router tree.

## Related Code
- `bot/routers/__init__.py`
- `bot/url_router.py`
- `tests/unit/bot/test_handler_registration.py`
