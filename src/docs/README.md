# Source Documentation Index

## Scope
This tree documents the runtime source in `src/` for engineering onboarding, debugging, and operational handoff.

## Navigation
- `docs/DOCS_STYLE.md` documentation template and quality bar
- `docs/api/` API routing and endpoint references
- `docs/apps/` domain models and business services
- `docs/bot/` bot runtime and onboarding FSM
- `docs/config/` settings and runtime entrypoint wiring
- `docs/core/` shared platform primitives
- `docs/scripts/` container/runtime shell operations
- `docs/tests/` test layout and critical scenario groups

## Maintenance Rules
- Keep docs mirrored to the owning code path where practical.
- When behavior changes, update matching docs in the same session/PR.
- API docs are endpoint-centric and should not duplicate Postman examples.

## Related Docs
- `../AGENTS.md`
- `../PROJECT.md`
- `../PROGRESS.md`
