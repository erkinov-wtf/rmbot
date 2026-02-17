# User Notification Service (`core/services/notifications.py`)

## Scope
Centralized user-facing notification orchestration for cross-domain events, currently delivered through Telegram bot chats.

## Public Events
- `notify_access_request_decision`: approval/rejection message to the requester Telegram ID.
- `notify_ticket_assigned`: assignment update to master plus technician-specific actionable message.
- `notify_ticket_started`: work-start update to assigned technician.
- `notify_ticket_waiting_qc`: waiting-QC update to QC reviewers (with inline approve/reject controls).
- `notify_ticket_qc_pass`: QC pass/closure + XP summary to assigned technician.
- `notify_ticket_qc_fail`: QC fail/rework update with technician-specific rework actions.

Ticket workflow notifications include:
- ticket id,
- inventory item serial number (from `ticket.inventory_item.serial_number`),
- actor and relevant assignee/QC context.

## Recipient Resolution Rules
- User-recipient notifications resolve through active `User` rows and linked active `TelegramProfile` rows.
- Role-recipient notifications resolve users by role slug (`qc_inspector`, `super_admin`) and then map to Telegram IDs.
- Actor user can be excluded per event to avoid self-notify spam.
- Technician action notifications are now split from manager/QC informational notifications so inline controls are only delivered to technician recipients.

## Telegram Inline Controls
- Technician ticket notifications can include inline buttons for Telegram-driven actions (`start`, `pause`, `resume`, `stop`, `to_waiting_qc`, `refresh`).
- Callback payloads are generated through `TechnicianTicketActionService` and use stable format `tt:<ticket_id>:<action>`.
- Action availability is resolved from ticket status + latest work-session status to prevent invalid transitions from stale buttons.
- Waiting-QC notifications include QC decision controls (`pass`, `fail`, `refresh`) with callback payload format `tqc:<ticket_id>:<action>` via `TicketQCActionService`.

## Delivery Behavior
- Telegram sends are best-effort and non-blocking for business transactions.
- Dispatch is deferred with `transaction.on_commit(...)` so notifications are emitted only after successful DB commit.
- Test runs skip outbound delivery (`settings.IS_TEST_RUN`).
- Missing `BOT_TOKEN` disables delivery with log-only skip behavior.
- Notification payloads are rendered as Telegram HTML cards (emoji + `<b>/<code>` formatting) for consistent UX in all lifecycle events.
- Dynamic text fields (names, serials, comments, statuses) are escaped before interpolation to keep HTML-safe rendering.
- Delivery now passes `parse_mode=settings.BOT_PARSE_MODE` (fallback `HTML`) on each `send_message` call.

## Failure Modes
- Missing or unlinked Telegram profiles for recipients results in a silent skip for that event.
- Per-recipient Telegram API failures are logged and do not break the surrounding workflow/API request.

## Related Code
- `core/services/notifications.py`
- `bot/services/technician_ticket_actions.py`
- `apps/account/services.py`
- `apps/ticket/services_workflow.py`
