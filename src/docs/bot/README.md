# Bot Docs Index

## Scope
Documents aiogram runtime lifecycle, middleware ordering, and class-based onboarding handler behavior.
Includes command-free technician and user menus via reply keyboard controls.
Ticket-admin controls now include permission-gated ticket intake and review actions.

## Navigation
- `docs/bot/runtime.md`
- `docs/bot/router_modules.md`
- `docs/bot/onboarding_fsm.md`
- `docs/bot/permissions.md`
- `docs/bot/technician_ticket_actions.md`
- `docs/bot/ticket_qc.md`
- `docs/bot/ticket_admin.md`
- `docs/bot/technician_tickets.md`

## Maintenance Rules
- Keep middleware order and runtime lifecycle docs aligned with loader/runtime changes.
- Keep bot routers class-based (`MessageHandler`/`CallbackQueryHandler`) and update docs/tests when adding new handlers.
- Keep router module split docs aligned with handler ownership changes (`router_modules.md`).
- Update onboarding FSM docs whenever bot input flow changes.
- Update permission docs whenever bot-visible capability gates change.
- Update QC callback docs whenever Telegram QC callback payloads/actions change.
- Update ticket-admin docs whenever intake/review callback payloads or role checks change.
- Update technician ticket docs whenever callback payloads/actions or `/queue` behavior changes.

## Related Code
- `bot/etc/loader.py`
- `bot/permissions.py`
- `bot/runtime.py`
- `bot/routers/start/__init__.py`
- `bot/routers/start/common.py`
- `bot/routers/start/access.py`
- `bot/routers/start/profile.py`
- `bot/routers/start/xp.py`
- `bot/routers/ticket_qc/__init__.py`
- `bot/routers/ticket_qc/base.py`
- `bot/routers/ticket_qc/entry.py`
- `bot/routers/ticket_qc/callbacks.py`
- `bot/routers/ticket_admin/__init__.py`
- `bot/routers/ticket_admin/create.py`
- `bot/routers/ticket_admin/create_entry.py`
- `bot/routers/ticket_admin/create_callbacks.py`
- `bot/routers/ticket_admin/review.py`
- `bot/routers/ticket_admin/review_entry.py`
- `bot/routers/ticket_admin/review_callbacks.py`
- `bot/routers/technician_tickets/__init__.py`
- `bot/routers/technician_tickets/entry.py`
- `bot/routers/technician_tickets/callbacks.py`
- `bot/services/ticket_qc_actions.py`
- `bot/services/ticket_qc_queue.py`
- `bot/services/technician_ticket_actions.py`
- `bot/webhook/views.py`
