# Bot Access Onboarding FSM

## Scope
Documents `/start` onboarding state machine, input validation, and account-request finalization behavior in class-based aiogram handlers.

## FSM States
- `first_name`
- `last_name`
- `phone`

## Execution Flow
1. User sends `/start`.
2. Router checks existing access state:
   - pending request -> short-circuit with pending message.
   - active linked user -> short-circuit as already registered.
3. FSM starts an editable "access request draft" message that shows field-by-field progress (`first_name`, `last_name`, `phone`).
4. After each successful step, the previous draft card is removed and replaced with an updated card showing saved values, progress bar, and the next action prompt.
5. Finalizer calls `AccountService.ensure_pending_access_request_from_bot`.
6. Bot returns result-specific confirmation text.

All onboarding command/button/message/callback entrypoints are implemented as class handlers split across:
- `bot/routers/start/access.py` (FSM and access-request flow)
- `bot/routers/start/profile.py` (help/profile handlers)
- `bot/routers/start/xp.py` (XP summary/history handlers and pagination callback)

## Invariants and Contracts
- Bot onboarding is the only public path to create access requests.
- At most one pending access request is effective per Telegram identity.
- Contact-based phone input must belong to the sender when `user_id` is provided.

## Validation and Failure Modes
- Name fields enforce minimum-length validation.
- Invalid phone format or foreign contact ownership is rejected.
- Service-layer business conflicts (already approved/linked/duplicate phone) are surfaced as user-safe messages.

## Operational Notes
- `/cancel` clears FSM state explicitly.
- Onboarding UX uses emoji-rich HTML formatting (`<b>`, `<code>`) and persistent progress card updates to make saved values and remaining gaps obvious.
- Once a valid onboarding step is consumed, the user's submitted message (name/phone) is deleted and the old draft card is removed to keep chat history clean.
- The standalone phone-instructions prompt is tracked and deleted after a valid phone input is consumed (or when flow is canceled/reset) to avoid leftover helper messages.
- If edit-in-place is unavailable for the draft card (message missing/not editable), the bot posts a new progress card and continues tracking from it.
- `/my` reflects effective onboarding state (pending/registered/not-registered) using emoji + HTML formatting (`<b>`, `<code>`) for readability, while still including dynamic profile fields (identity, level/roles, XP totals, and technician counters where applicable).
- Bottom reply-keyboard menu is shown for non-FSM interactions to reduce slash-command usage:
  - common: `📊 My Profile`, `❓ Help`
  - unregistered: `📝 Start Access Request`
  - ticket admins (permission-gated): `🆕 Create Ticket`, `🧾 Review Tickets`
  - technician: `🎟 Active Tickets`, `🧪 Under QC`, `✅ Past Tickets`, `⭐ My XP`, `📜 XP Activity`
- `/xp_history` now renders 5 activity rows per page with an always-visible inline pagination row (`<`, `X/Y`, `>`), using callback data format `xph:<limit>:<offset>` and message edit-in-place navigation.
- XP summary/history text intentionally avoids raw enum/reference values and surfaces user-facing reason labels instead.
- `/help` is role/status-aware and renders sectioned command blocks with formatting:
  - always: core commands (`/my`, `/help`, `/cancel`)
  - pending/unregistered: `/start` with contextual description
  - permission-gated ticket-admin commands (`/ticket_create`, `/ticket_review`)
  - technician command set (`/queue`, `/active`, `/tech`, `/under_qc`, `/past`, `/xp`, `/xp_history`)
  - QC command (`/qc_checks`) when QC permission is granted
- `/help` hides `📝 Start Access Request` for pending users (even when linked user is inactive/missing) by checking pending-request state directly.

## Related Code
- `bot/routers/start/__init__.py`
- `bot/routers/start/common.py`
- `bot/routers/start/access.py`
- `bot/routers/start/profile.py`
- `bot/routers/start/xp.py`
- `apps/account/services.py`
- `apps/account/models.py`
