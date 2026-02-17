# Ticket Admin Bot Controls

## Scope
Documents Telegram ticket-intake and ticket-review handlers for users with create/review ticket permissions.

## Execution Flows
- Reply-keyboard entrypoints:
  - `🆕 Create Ticket` or `/ticket_create`
  - `🧾 Review Tickets` or `/ticket_review`
- Ticket intake callback flow (`tc:*`), inline-only:
  1. Select inventory item from paginated inline list (`tc:list:<page>`, `tc:item:<item_id>:<page>`), 5 items per page.
  2. Toggle parts using inline buttons (`tc:tog:<part_id>`), then continue (`tc:go`).
  3. Configure each selected part with inline color/minutes controls (`tc:clr:*`, `tc:min:*`, `tc:adj:*`, `tc:save`).
  4. Confirm summary and create (`tc:create`), or cancel/back (`tc:cancel`, `tc:back`).
- Ticket review callback flow:
  - Queue callbacks (`trq:*`): `trq:refresh:<page>`, `trq:open:<ticket_id>:<page>`.
  - Detail action callbacks (`tra:*`):
    - Approve + assign flow: open technician picker (`tra:assign:<ticket_id>`), paginate (`tra:ap:<ticket_id>:<page>`), then execute (`tra:at:<ticket_id>:<technician_id>`).
    - Manual metrics flow: open editor (`tra:manual:<ticket_id>`), mutate color/xp (`tra:mc`, `tra:mx`, `tra:adj`), save (`tra:ms`).
    - Return to ticket detail (`tra:bk:<ticket_id>`).
- Ticket create/review callback steps stay inline-driven, but users can switch context at any time with reply-keyboard buttons or commands (state is cleared by those entrypoints).

## Invariants and Contracts
- Menu-button visibility is permission-gated from `resolve_ticket_bot_permissions`.
- Reply-keyboard entrypoint labels and inline action labels are localized per Telegram user locale (`en`, `ru`, `uz`), while callback payloads stay locale-agnostic.
- Every message/callback action re-checks permissions before execution.
- Assign flow validates selected technician has active `TECHNICIAN` role.
- Review queue/detail data always loads from current DB state before rendering.
- Create flow enforces active-ticket guard on selected inventory items before part selection.
- List-style bot screens use fixed page size `5` and append a fixed inline pagination row (`<`, `X/Y`, `>`) after list rows.
- Pagination callbacks are clamped, so tapping previous/next at boundaries never moves out of range.

## Failure Modes
- Unknown callback payloads are rejected with safe alert responses.
- Missing registration returns access-request guidance and start-access keyboard.
- Invalid callback args (IDs/colors/minutes/xp deltas) keep FSM active and show corrective alerts.
- Workflow/domain validation errors (invalid transitions, missing ticket) are surfaced to the operator.

## Related Code
- `bot/routers/ticket_admin.py`
- `bot/permissions.py`
- `api/v1/ticket/serializers/ticket.py`
- `apps/ticket/services_workflow.py`
