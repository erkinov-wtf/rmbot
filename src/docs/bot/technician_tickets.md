# Technician Ticket Bot Controls

## Scope
Documents Telegram command/callback handlers that let technicians run ticket workflow and work-session actions directly from inline bot buttons.

## Execution Flows
- Reply-keyboard entrypoints (`Active Tickets`, `Under QC Tickets`, `Past Tickets`) and command aliases (`/queue`, `/active`, `/tech`, `/under_qc`, `/past`) open technician ticket dashboards by scope.
- Dashboard view renders a scoped ticket list with inline buttons (`open`, `refresh queue`).
- Queue callback flow (`ttq:<action>:<scope>` and `ttq:open:<ticket_id>:<scope>`):
  1. Parse queue callback payload.
  2. Validate active linked user + technician role.
  3. Either refresh dashboard or open one ticket control card.
  4. Edit source message with latest queue/ticket state.
- Ticket callback flow (`tt:<ticket_id>:<action>`):
  1. Parse callback payload.
  2. Validate active linked user + technician role.
  3. Execute ticket action through `TechnicianTicketActionService`.
  4. Edit source message with refreshed ticket state and next available buttons + back-to-queue navigation.

## Invariants and Contracts
- Only active linked users with technician role can run ticket action callbacks.
- Action execution is ownership-scoped (`ticket.technician_id` must match callback actor).
- `start` is suppressed on assigned/rework tickets while technician has any other open session (`RUNNING`/`PAUSED`).
- Ticket dashboards are scope-filtered:
  - `active`: `assigned`, `rework`, `in_progress`
  - `under_qc`: `waiting_qc`
  - `past`: `done`
- Callback message editing is best-effort; "message is not modified" errors are ignored safely.

## Failure Modes
- Invalid callback payloads return user-safe alert (`Unknown action`).
- Missing registration returns alert plus a follow-up chat message with bottom-menu access button (`Start Access Request`).
- Role mismatch returns user-safe alert.
- Domain validation errors (invalid transition, missing active session) are surfaced as callback alerts.

## Operational Notes
- Queue callback parser keeps backward compatibility for legacy payloads without scope and defaults them to `active`.
- Ticket cards always include a back-to-queue inline button so operators can stay in-chat without commands.
- Bottom reply-keyboard buttons provide command-free entry for common technician actions.
- Message refresh uses service-driven action resolution so stale buttons self-correct after any action.

## Related Code
- `bot/routers/technician_tickets.py`
- `bot/middlewares/auth.py`
- `apps/ticket/services_technician_actions.py`
