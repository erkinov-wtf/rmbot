# Bot Docs Index

## Scope
Documents aiogram runtime lifecycle, middleware ordering, and onboarding handler behavior.

## Navigation
- `docs/bot/runtime.md`
- `docs/bot/onboarding_fsm.md`
- `docs/bot/technician_tickets.md`

## Maintenance Rules
- Keep middleware order and runtime lifecycle docs aligned with loader/runtime changes.
- Update onboarding FSM docs whenever bot input flow changes.
- Update technician ticket docs whenever callback payloads/actions or `/queue` behavior changes.

## Related Code
- `bot/etc/loader.py`
- `bot/runtime.py`
- `bot/routers/start.py`
- `bot/routers/technician_tickets.py`
- `bot/webhook/views.py`
