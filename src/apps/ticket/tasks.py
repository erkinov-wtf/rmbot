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
            delivery_results.append(
                SLAAutomationEscalationService.deliver_for_event_id(event_id=event_id)
            )
        except Exception:
            logger.exception(
                "SLA escalation delivery failed for event_id=%s.",
                event_id,
            )
            delivery_results.append(
                {
                    "event_id": event_id,
                    "delivered": False,
                    "channels": [],
                    "reason": "delivery_error",
                }
            )

    result["delivery"] = delivery_results
    return result
