# SLA Escalation Service (`apps/ticket/services_sla_escalation.py`)

## Scope
Delivers SLA events to external channels and records delivery attempts for retry/audit behavior.

## Execution Flows
- Resolve route and channels from `sla.escalation` rules.
- Build message payloads (telegram/email/webhook).
- Deliver across selected channels.
- Derive retryability and attempt status.
- Persist `SLAAutomationDeliveryAttempt` records.

## Invariants and Contracts
- First matching route wins; otherwise default channels apply.
- Successful prior delivery for event short-circuits later attempts.
- Attempt rows are append-only event history.

## Side Effects
- Outbound network calls (Telegram API, email backend, ops webhook).
- Delivery attempt row creation for every task execution path.

## Failure Modes
- Routing disabled/no channels routed.
- No channel configuration present.
- Channel-specific delivery errors with retryable/non-retryable classification.

## Operational Notes
- Retry/backoff orchestration is executed in Celery task layer.
- Non-retryable reasons prevent further retries even when delivery fails.

## Related Code
- `apps/ticket/models.py`
- `apps/ticket/tasks.py`
- `apps/rules/services.py`
