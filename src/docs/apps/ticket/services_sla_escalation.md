# SLA Escalation Service (`apps/ticket/services_sla_escalation.py`)

## Scope
Delivers SLA events to external channels and records append-only delivery attempts for retry/audit behavior.

## Execution Flows
- Resolve route and channels from `sla.escalation` rules.
- Build message payloads (telegram/email/webhook).
- Deliver across selected channels.
- Derive retryability from channel outcomes.
- Persist `SLAAutomationDeliveryAttempt` rows per task execution.

## Service vs Domain Responsibilities
- Service-owned:
  - routing and channel selection,
  - transport calls and retryability classification.
- Model/manager-owned:
  - event fetch by id (`SLAAutomationEvent.domain.get_by_id`),
  - idempotency success check (`SLAAutomationDeliveryAttempt.domain.has_success_for_event`),
  - attempt persistence mapping (`SLAAutomationDeliveryAttempt.create_from_delivery_response`),
  - event payload helpers (`SLAAutomationEvent.payload_data`, `is_repeat`).

## Invariants and Contracts
- First matching route wins; fallback uses default channels.
- Prior successful delivery short-circuits duplicate delivery work.
- Attempt rows remain append-only audit history.

## Side Effects
- Outbound network calls (Telegram API, email backend, ops webhook).
- Delivery-attempt persistence for each run path (success/failure/skipped).

## Failure Modes
- Routing disabled/no routed channels.
- No channel configuration present.
- Channel-specific delivery errors with retryable/non-retryable classification.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/managers.py`
- `apps/ticket/tasks.py`
- `apps/rules/services.py`
