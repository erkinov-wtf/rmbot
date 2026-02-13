from __future__ import annotations

import logging

from celery import shared_task

from ticket.services_sla import SLAAutomationService
from ticket.services_sla_escalation import SLAAutomationEscalationService
from ticket.services_stockout import StockoutIncidentService

logger = logging.getLogger(__name__)


@shared_task(name="ticket.tasks.detect_stockout_incidents")
def detect_stockout_incidents() -> dict[str, object]:
    return StockoutIncidentService.detect_and_sync()


@shared_task(bind=True, name="ticket.tasks.deliver_sla_automation_event")
def deliver_sla_automation_event(self, *, event_id: int) -> dict[str, object]:
    retry_count = int(getattr(self.request, "retries", 0))
    attempt_number = retry_count + 1
    max_retries = SLAAutomationEscalationService.max_retries()

    response = SLAAutomationEscalationService.deliver_for_event_id(event_id=event_id)
    should_retry = (
        SLAAutomationEscalationService.is_retryable_failure(response=response)
        and retry_count < max_retries
    )
    retry_backoff_seconds = 0
    if should_retry:
        retry_backoff_seconds = SLAAutomationEscalationService.retry_backoff_seconds(
            retry_index=retry_count + 1
        )

    attempt = SLAAutomationEscalationService.record_attempt(
        event_id=event_id,
        attempt_number=attempt_number,
        task_id=str(getattr(self.request, "id", "") or ""),
        response=response,
        should_retry=should_retry,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    result = {
        **response,
        "attempt_id": attempt.id if attempt else None,
        "attempt_number": attempt_number,
        "should_retry": should_retry,
        "retry_backoff_seconds": retry_backoff_seconds,
    }

    if should_retry:
        logger.warning(
            "SLA escalation delivery attempt failed. event_id=%s attempt=%s retry_in=%ss",
            event_id,
            attempt_number,
            retry_backoff_seconds,
        )
        raise self.retry(
            countdown=retry_backoff_seconds,
            max_retries=max_retries,
        )

    return result


@shared_task(name="ticket.tasks.evaluate_sla_automation")
def evaluate_sla_automation() -> dict[str, object]:
    result = SLAAutomationService.evaluate_and_act()
    delivery_results: list[dict[str, object]] = []
    for row in result.get("results", []):
        if not isinstance(row, dict) or not row.get("event_created"):
            continue
        event_id = row.get("event_id")
        if not isinstance(event_id, int):
            continue
        try:
            deliver_sla_automation_event.delay(event_id=event_id)
            delivery_results.append(
                {
                    "event_id": event_id,
                    "queued": True,
                }
            )
        except Exception:
            logger.exception(
                "SLA escalation delivery enqueue failed for event_id=%s.",
                event_id,
            )
            delivery_results.append(
                {
                    "event_id": event_id,
                    "queued": False,
                    "reason": "delivery_enqueue_error",
                }
            )

    result["delivery"] = delivery_results
    return result
