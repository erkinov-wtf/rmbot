# Bot Access Onboarding FSM

## Scope
Documents `/start` onboarding state machine, input validation, and account-request finalization behavior.

## FSM States
- `first_name`
- `last_name`
- `phone`

## Execution Flow
1. User sends `/start`.
2. Router checks existing access state:
   - pending request -> short-circuit with pending message.
   - active linked user -> short-circuit as already registered.
3. FSM collects profile fields and normalized phone.
4. Finalizer calls `AccountService.ensure_pending_access_request_from_bot`.
5. Bot returns result-specific confirmation text.

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
- `/my` reflects effective onboarding state (pending/registered/not-registered) with expanded account details (name, username, phone, level, roles, XP totals, and technician ticket counters for active/waiting-QC/done).
- Bottom reply-keyboard menu is shown for non-FSM interactions to reduce slash-command usage:
  - common: `My Status`, `Help`
  - unregistered: `Start Access Request`
  - technician: `Active Tickets`, `Under QC Tickets`, `Past Tickets`, `My XP`, `XP History`
- `/help` still exposes command hints for recovery paths, including technician dashboard aliases (`/queue`, `/active`, `/tech`, `/under_qc`, `/past`) and XP shortcuts (`/xp`, `/xp_history`).

## Related Code
- `bot/routers/start.py`
- `apps/account/services.py`
- `apps/account/models.py`
