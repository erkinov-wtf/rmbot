from __future__ import annotations

from celery import shared_task

from ticket.services_stockout import StockoutIncidentService


@shared_task(name="ticket.tasks.detect_stockout_incidents")
def detect_stockout_incidents() -> dict[str, object]:
    return StockoutIncidentService.detect_and_sync()
