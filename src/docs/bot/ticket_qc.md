# QC Ticket Bot Controls

## Scope
Documents class-based Telegram QC handlers that allow QC inspectors to open their assigned QC queue from the bot keyboard and approve or reject tickets directly in Telegram.

## Execution Flow
- QC queue entrypoints:
  - Reply-keyboard button `🧪 QC Checks`
  - Commands `/qc_checks` and `/qc`
- QC queue callback payloads (`tqq:*`):
  - `tqq:refresh:<page>`
  - `tqq:open:<ticket_id>:<page>`
- Queue lists assigned checks for current user (`ticket.master_id == current_user.id`) in pages of 5 rows and appends fixed pagination controls (`<`, `X/Y`, `>`).
- Waiting-QC notification sends inline controls built from `TicketQCActionService` callback payloads:
  - `tqc:<ticket_id>:pass`
  - `tqc:<ticket_id>:fail`
  - `tqc:<ticket_id>:refresh`
- QC callback handler (`bot/routers/ticket_qc/callbacks.py`) flow:
  1. Parse and validate callback payload.
  2. Validate active linked user.
  3. Validate QC permission via bot permission mapping (`resolve_ticket_bot_permissions(...).can_qc`).
  4. Resolve ticket and validate status for QC decisions.
  5. Execute workflow transition (`qc_pass_ticket` or `qc_fail_ticket`) when action is decision, including Telegram-source transition metadata (`source/channel/telegram_action`).
  6. Re-read ticket and edit message with refreshed state + next action keyboard.
- All QC command/button/callback handlers are class-based and split by job:
  - shared classmethod helpers: `bot/routers/ticket_qc/base.py`
  - entrypoints: `bot/routers/ticket_qc/entry.py`
  - callbacks: `bot/routers/ticket_qc/callbacks.py`

## Invariants and Contracts
- QC decision actions are allowed only when ticket status is `WAITING_QC`.
- For non-`WAITING_QC` statuses, only `refresh` remains available.
- QC decision transitions are explicitly tagged as Telegram-originated in transition metadata for audit/log visibility.
- Callback payload formats are stable and locale-agnostic (`tqq:*` for queue, `tqc:*` for actions).
- Labels/messages are localized through Django i18n (`en`, `ru`, `uz`) using Telegram `language_code`.
- Message editing is safe against "message is not modified" errors.
- Queue pagination is page-clamped and never goes out of bounds.
- Queue/detail screens keep a back-navigation button to return to the same queue page.

## Failure Modes
- Invalid payloads return safe callback alert (`Unknown action`).
- Inactive/unlinked users receive access guidance.
- Non-QC users receive explicit permission alert.
- Missing ticket or invalid status returns actionable callback alert.
- Workflow validation errors are surfaced from domain service as callback alerts.

## Related Code
- `bot/routers/ticket_qc/__init__.py`
- `bot/routers/ticket_qc/base.py`
- `bot/routers/ticket_qc/entry.py`
- `bot/routers/ticket_qc/callbacks.py`
- `bot/services/ticket_qc_actions.py`
- `bot/services/ticket_qc_queue.py`
- `bot/permissions.py`
- `core/services/notifications.py`
- `apps/ticket/services_workflow.py`
