# User Notification Service (`core/services/notifications.py`)

## Scope
Centralized user-facing notification orchestration for cross-domain events, currently delivered through Telegram bot chats.

## Public Events
- `notify_access_request_decision`: approval/rejection message to the requester Telegram ID.
- `notify_ticket_assigned`: assignment update to master + technician.
- `notify_ticket_started`: work-start update to ticket master.
- `notify_ticket_waiting_qc`: waiting-QC update to QC inspectors + master.
- `notify_ticket_qc_pass`: QC pass/closure + XP summary to master + technician.
- `notify_ticket_qc_fail`: QC fail/rework update to master + technician.

Ticket workflow notifications include:
- ticket id,
- inventory item serial number (from `ticket.inventory_item.serial_number`),
- actor and relevant assignee/QC context.

## Recipient Resolution Rules
- User-recipient notifications resolve through active `User` rows and linked active `TelegramProfile` rows.
- Role-recipient notifications resolve users by role slug (`qc_inspector`) and then map to Telegram IDs.
- Actor user can be excluded per event to avoid self-notify spam.

## Delivery Behavior
- Telegram sends are best-effort and non-blocking for business transactions.
- Dispatch is deferred with `transaction.on_commit(...)` so notifications are emitted only after successful DB commit.
- Test runs skip outbound delivery (`settings.IS_TEST_RUN`).
- Missing `BOT_TOKEN` disables delivery with log-only skip behavior.

## Failure Modes
- Missing or unlinked Telegram profiles for recipients results in a silent skip for that event.
- Per-recipient Telegram API failures are logged and do not break the surrounding workflow/API request.

## Related Code
- `core/services/notifications.py`
- `apps/account/services.py`
- `apps/ticket/services_workflow.py`
