# Technician Ticket Bot Controls

## Scope
Documents Telegram command/callback handlers that let technicians run ticket workflow and work-session actions directly from inline bot buttons.

## Execution Flows
- `/queue`: lists technician-owned actionable tickets and sends one message per ticket with inline controls.
- Callback flow (`tt:<ticket_id>:<action>`):
  1. Parse callback payload.
  2. Validate active linked user + technician role.
  3. Execute ticket action through `TechnicianTicketActionService`.
  4. Edit source message with refreshed ticket state and next available buttons.

## Invariants and Contracts
- Only active linked users with technician role can run ticket action callbacks.
- Action execution is ownership-scoped (`ticket.technician_id` must match callback actor).
- `start` is suppressed on assigned/rework tickets while technician has any other open session (`RUNNING`/`PAUSED`).
- Callback message editing is best-effort; "message is not modified" errors are ignored safely.

## Failure Modes
- Invalid callback payloads return user-safe alert (`Unknown action`).
- Missing registration/role mismatch returns user-safe alert.
- Domain validation errors (invalid transition, missing active session) are surfaced as callback alerts.

## Operational Notes
- `/queue` intentionally returns only actionable statuses (`assigned`, `rework`, `in_progress`).
- Message refresh uses service-driven action resolution so stale buttons self-correct after any action.

## Related Code
- `bot/routers/technician_tickets.py`
- `bot/middlewares/auth.py`
- `apps/ticket/services_technician_actions.py`
