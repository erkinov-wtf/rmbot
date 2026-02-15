# Domain Apps Docs Index

## Scope
Documents business-domain modules in `apps/` with focus on models, services, and invariants.

## Navigation
- `docs/apps/account/README.md`
- `docs/apps/attendance/README.md`
- `docs/apps/inventory/README.md`
- `docs/apps/gamification/README.md`
- `docs/apps/payroll/README.md`
- `docs/apps/rules/README.md`
- `docs/apps/ticket/README.md`

## Maintenance Rules
- Keep `models.py` docs in `docs/apps/<app>/models.md`.
- Keep business service docs in `docs/apps/<app>/services.md` or `services_*.md`.
- For complex flows, include invariants, side effects, and failure modes.

## Related Code
- `apps/`
