# Technician Telegram Actions Service (`apps/ticket/services_technician_actions.py`)

## Scope
Resolves technician-allowed ticket actions for Telegram, executes selected actions through existing workflow/session services, and builds callback/keyboard payloads for inline bot controls.

## Execution Flows
- `queue_states_for_technician`: returns actionable ticket snapshots for `/queue` bot command.
- `view_states_for_technician`: returns technician ticket snapshots for a specific scope (`active`, `under_qc`, `past`).
- `state_for_technician_and_ticket`: resolves one technician-owned ticket and current available actions plus XP context (`potential_xp`, `acquired_xp`).
- `execute_for_technician`: validates ownership + action availability, performs action (`start/pause/resume/stop/to_waiting_qc`), then returns refreshed state.
- Queue helpers (`render_queue_summary`, `build_queue_keyboard`, `build_queue_callback_data`, `parse_queue_callback_data`) drive queue-list and scoped refresh navigation in chat.
- `build_action_keyboard` + ticket callback helpers render inline action controls for a specific ticket card; `scope_for_ticket_status` selects the correct back-navigation scope after state changes.

## Invariants and Contracts
- Technician ownership is mandatory (`ticket.technician_id == actor_user_id`) for both state reads and action execution.
- Available action set depends on ticket status + latest session status:
  - `ASSIGNED`/`REWORK` -> `start` only when technician has no other open work session
  - `IN_PROGRESS` + `RUNNING` -> `pause`, `stop`
  - `IN_PROGRESS` + `PAUSED` -> `resume`, `stop`
  - `IN_PROGRESS` + `STOPPED` -> `to_waiting_qc`
- Callback payload format is stable: `tt:<ticket_id>:<action>`.
- Queue payload format is scope-aware: `ttq:refresh:<scope>` and `ttq:open:<ticket_id>:<scope>` (legacy payloads without scope are still parsed as `active`).

## Side Effects
- Delegates to domain orchestration services (`TicketWorkflowService`, `TicketWorkSessionService`) for all state mutations.
- Reuses existing transition logging, inventory updates, XP side effects, and notification hooks from those services.

## Failure Modes
- Ticket not found for technician ownership returns user-safe validation error.
- Unsupported or currently unavailable action returns validation error.
- Underlying workflow/session domain validation errors are propagated (for example, invalid transition state).

## Operational Notes
- Keyboard rendering automatically appends a `refresh` action while actionable buttons exist.
- Queue summaries are scope-aware for both empty-state text and total counters (`active`, `under_qc`, `past`).
- Queue lines expose ticket status + XP progress (`acquired/potential`) and ticket-detail cards show explicit `Potential XP`, `Acquired XP`, and `XP progress`.
- Inline labels are action-specific (`Start work`, `Pause work`, `Send to QC`, `Refresh list/ticket`) to keep button intent explicit in Telegram UI.
- Scope listing rules:
  - `active` -> `assigned`, `rework`, `in_progress`
  - `under_qc` -> `waiting_qc`
  - `past` -> `done`

## Related Code
- `apps/ticket/services_technician_actions.py`
- `apps/ticket/services_workflow.py`
- `apps/ticket/services_work_session.py`
- `bot/routers/technician_tickets.py`
