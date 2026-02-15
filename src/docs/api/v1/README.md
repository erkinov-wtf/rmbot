# API v1 Endpoint Reference

## Scope
Entry index for endpoint-centric technical docs under `/api/v1/`.

## Access Model
- Default: JWT-authenticated endpoints.
- Public exceptions: auth/token endpoints and misc health/test.
- Role-gated domains: users moderation, analytics, rules, ticket actions.

## Endpoint Reference
- Users + access moderation: `docs/api/v1/account/README.md`
- Attendance: `docs/api/v1/attendance/README.md`
- Inventory + serial-number suggestions: `docs/api/v1/inventory/README.md`
- Core auth/analytics/misc: `docs/api/v1/core/README.md`
- XP ledger: `docs/api/v1/gamification/README.md`
- Rules config versioning + rollback: `docs/api/v1/rules/README.md`
- Ticket lifecycle + work sessions: `docs/api/v1/ticket/README.md`

## Validation and Failure Modes
- Most endpoints follow shared response envelope from `core.api.views`.
- Validation/permission failures are normalized by global exception handler.
- Some misc endpoints intentionally return raw payloads for probe/smoke use.

## Operational Notes
- API request/response examples are maintained in Postman, not in `src/docs`.
- Keep endpoint docs synchronized with route/view behavior in same session/PR.

## Related Code
- `api/v1/urls.py`
- `api/v1/`
- `core/api/views.py`
- `core/api/exceptions.py`
