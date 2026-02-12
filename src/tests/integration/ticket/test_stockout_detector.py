from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from core.utils.constants import BikeStatus, TicketStatus, TicketTransitionAction
from ticket.models import StockoutIncident, TicketTransition
from ticket.services_stockout import StockoutIncidentService

pytestmark = pytest.mark.django_db

BUSINESS_TZ = ZoneInfo("Asia/Tashkent")


def test_stockout_detector_starts_and_resolves_incident(
    bike_factory,
):
    bike_factory(bike_code="RM-SO-0001", status=BikeStatus.IN_SERVICE, is_active=True)

    started_at = datetime(2026, 2, 9, 11, 0, tzinfo=BUSINESS_TZ)
    started_summary = StockoutIncidentService.detect_and_sync(now_utc=started_at)
    assert started_summary["action"] == "started"

    incident = StockoutIncident.objects.get(pk=started_summary["incident_id"])
    assert incident.is_active is True
    assert incident.ended_at is None

    bike_factory(bike_code="RM-SO-0002", status=BikeStatus.READY, is_active=True)
    resolved_at = started_at + timedelta(minutes=17)
    resolved_summary = StockoutIncidentService.detect_and_sync(now_utc=resolved_at)
    assert resolved_summary["action"] == "resolved"

    incident.refresh_from_db()
    assert incident.is_active is False
    assert incident.duration_minutes == 17
    assert incident.ready_count_at_end == 1


def test_stockout_detector_ignores_non_business_window(
    bike_factory,
):
    bike_factory(bike_code="RM-SO-1001", status=BikeStatus.BLOCKED, is_active=True)

    non_business_time = datetime(2026, 2, 9, 21, 30, tzinfo=BUSINESS_TZ)
    summary = StockoutIncidentService.detect_and_sync(now_utc=non_business_time)

    assert summary["action"] == "no_change_idle"
    assert StockoutIncident.objects.count() == 0


def test_monthly_sla_snapshot_contains_qc_and_stockout_stats(
    ticket_factory,
    bike_factory,
    user_factory,
):
    master = user_factory(
        username="stockout_master",
        first_name="Stockout Master",
        email="stockout_master@example.com",
    )
    technician = user_factory(
        username="stockout_technician",
        first_name="Stockout Tech",
        email="stockout_technician@example.com",
    )
    first_pass_ticket = ticket_factory(
        bike=bike_factory(bike_code="RM-SLA-0001"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=datetime(2026, 1, 8, 14, 0, tzinfo=BUSINESS_TZ),
    )
    rework_ticket = ticket_factory(
        bike=bike_factory(bike_code="RM-SLA-0002"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=datetime(2026, 1, 9, 16, 0, tzinfo=BUSINESS_TZ),
    )
    TicketTransition.objects.create(
        ticket=rework_ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.REWORK,
        action=TicketTransitionAction.QC_FAIL,
        actor=master,
    )
    TicketTransition.objects.create(
        ticket=first_pass_ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=master,
    )
    StockoutIncident.objects.create(
        started_at=datetime(2026, 1, 10, 10, 0, tzinfo=BUSINESS_TZ),
        ended_at=datetime(2026, 1, 10, 10, 25, tzinfo=BUSINESS_TZ),
        is_active=False,
        duration_minutes=25,
        ready_count_at_start=0,
        ready_count_at_end=2,
    )

    snapshot = StockoutIncidentService.monthly_sla_snapshot(
        month_start_dt=datetime(2026, 1, 1, 0, 0, tzinfo=BUSINESS_TZ),
        next_month_start_dt=datetime(2026, 2, 1, 0, 0, tzinfo=BUSINESS_TZ),
    )

    assert snapshot["stockout"]["incidents"] == 1
    assert snapshot["stockout"]["minutes"] == 25
    assert snapshot["qc"]["done"] == 2
    assert snapshot["qc"]["first_pass_done"] == 1
    assert snapshot["qc"]["first_pass_rate_percent"] == 50.0
