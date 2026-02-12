from datetime import timedelta

import pytest
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import (
    BikeStatus,
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
    XPLedgerEntryType,
)
from gamification.models import XPLedger
from ticket.models import Ticket, TicketTransition

pytestmark = pytest.mark.django_db

FLEET_URL = "/api/v1/analytics/fleet/"
TEAM_URL = "/api/v1/analytics/team/"


@pytest.fixture
def analytics_users(user_factory, assign_roles):
    ops_user = user_factory(
        username="ops_analytics",
        first_name="Ops",
        email="ops_analytics@example.com",
    )
    assign_roles(ops_user, RoleSlug.OPS_MANAGER)

    regular_user = user_factory(
        username="regular_analytics",
        first_name="Regular",
        email="regular_analytics@example.com",
    )
    master_user = user_factory(
        username="master_analytics",
        first_name="Master",
        email="master_analytics@example.com",
    )
    assign_roles(master_user, RoleSlug.MASTER)

    technician_user = user_factory(
        username="tech_analytics",
        first_name="Tech",
        email="tech_analytics@example.com",
    )
    assign_roles(technician_user, RoleSlug.TECHNICIAN)

    return {
        "ops": ops_user,
        "regular": regular_user,
        "master": master_user,
        "technician": technician_user,
    }


def test_analytics_endpoints_require_auth(api_client):
    assert api_client.get(FLEET_URL).status_code == 401
    assert api_client.get(TEAM_URL).status_code == 401


def test_analytics_endpoints_require_ops_or_super_admin(
    authed_client_factory, analytics_users
):
    client = authed_client_factory(analytics_users["regular"])

    assert client.get(FLEET_URL).status_code == 403
    assert client.get(TEAM_URL).status_code == 403


def test_fleet_analytics_returns_operational_counters(
    authed_client_factory, analytics_users, bike_factory
):
    master = analytics_users["master"]
    technician = analytics_users["technician"]

    bike_ready = bike_factory(
        bike_code="RM-FA-0001", status=BikeStatus.READY, is_active=True
    )
    bike_in_service = bike_factory(
        bike_code="RM-FA-0002", status=BikeStatus.IN_SERVICE, is_active=True
    )
    bike_waiting_qc = bike_factory(
        bike_code="RM-FA-0003", status=BikeStatus.READY, is_active=True
    )
    bike_done = bike_factory(
        bike_code="RM-FA-0004", status=BikeStatus.READY, is_active=True
    )
    bike_factory(bike_code="RM-FA-0005", status=BikeStatus.WRITE_OFF, is_active=True)
    bike_factory(bike_code="RM-FA-0006", status=BikeStatus.READY, is_active=False)

    Ticket.objects.create(
        bike=bike_ready,
        master=master,
        technician=technician,
        status=TicketStatus.NEW,
        title="New ticket",
        flag_minutes=10,
    )
    Ticket.objects.create(
        bike=bike_in_service,
        master=master,
        technician=technician,
        status=TicketStatus.IN_PROGRESS,
        title="In progress ticket",
        flag_minutes=75,
    )
    Ticket.objects.create(
        bike=bike_waiting_qc,
        master=master,
        technician=technician,
        status=TicketStatus.WAITING_QC,
        title="Waiting QC ticket",
        flag_minutes=130,
    )
    Ticket.objects.create(
        bike=bike_done,
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=timezone.now(),
        title="Done ticket",
        flag_minutes=5,
    )

    client = authed_client_factory(analytics_users["ops"])
    resp = client.get(FLEET_URL)

    assert resp.status_code == 200
    data = resp.data["data"]
    assert data["fleet"]["total"] == 6
    assert data["fleet"]["active"] == 4
    assert data["tickets"]["new"] == 1
    assert data["tickets"]["in_progress"] == 1
    assert data["tickets"]["waiting_qc"] == 1
    assert data["tickets"]["done"] == 1
    assert data["backlog"]["flag_buckets"]["green"] == 1
    assert data["backlog"]["flag_buckets"]["red"] == 1
    assert data["backlog"]["flag_buckets"]["black"] == 1
    assert data["backlog"]["status_buckets"]["new"] == 1
    assert data["backlog"]["status_buckets"]["in_progress"] == 1
    assert data["backlog"]["kpis"]["red_or_worse_count"] == 2
    assert data["backlog"]["kpis"]["black_or_worse_count"] == 1
    assert data["backlog"]["kpis"]["avg_flag_minutes"] == 71.67
    assert (
        data["sla"]["availability"]["percent"] == data["kpis"]["availability_percent"]
    )
    assert data["sla"]["backlog_pressure"]["red_or_worse"] == 2
    assert data["qc"]["window_days"] == 7
    assert len(data["qc"]["trend"]) == 7
    assert data["stockout_incidents"]["window_days"] == 30


def test_fleet_analytics_returns_qc_trend_and_totals(
    authed_client_factory, analytics_users, bike_factory
):
    master = analytics_users["master"]
    technician = analytics_users["technician"]
    now = timezone.now()

    first_pass_ticket = Ticket.objects.create(
        bike=bike_factory(bike_code="RM-QC-0001"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=now - timedelta(days=1),
        title="QC first pass",
        flag_minutes=15,
    )
    rework_ticket = Ticket.objects.create(
        bike=bike_factory(bike_code="RM-QC-0002"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=now,
        title="QC with rework",
        flag_minutes=95,
    )

    TicketTransition.objects.create(
        ticket=first_pass_ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=master,
    )
    TicketTransition.objects.create(
        ticket=rework_ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.REWORK,
        action=TicketTransitionAction.QC_FAIL,
        actor=master,
    )
    TicketTransition.objects.create(
        ticket=rework_ticket,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=master,
    )

    client = authed_client_factory(analytics_users["ops"])
    resp = client.get(FLEET_URL)

    assert resp.status_code == 200
    qc = resp.data["data"]["qc"]
    assert qc["totals"]["done"] == 2
    assert qc["totals"]["first_pass_done"] == 1
    assert qc["totals"]["rework_done"] == 1
    assert qc["totals"]["first_pass_rate_percent"] == 50.0
    assert qc["totals"]["qc_pass_events"] == 2
    assert qc["totals"]["qc_fail_events"] == 1
    assert any(day["first_pass_done"] == 1 for day in qc["trend"])
    assert any(day["rework_done"] == 1 for day in qc["trend"])


def test_team_analytics_returns_member_metrics(
    authed_client_factory, analytics_users, bike_factory
):
    master = analytics_users["master"]
    technician = analytics_users["technician"]
    now = timezone.now()

    ticket_first_pass = Ticket.objects.create(
        bike=bike_factory(bike_code="RM-TA-0001"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=now - timedelta(days=1),
        title="First pass",
        flag_minutes=10,
    )
    ticket_rework = Ticket.objects.create(
        bike=bike_factory(bike_code="RM-TA-0002"),
        master=master,
        technician=technician,
        status=TicketStatus.DONE,
        done_at=now,
        title="Had rework",
        flag_minutes=80,
    )
    TicketTransition.objects.create(
        ticket=ticket_rework,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.REWORK,
        action=TicketTransitionAction.QC_FAIL,
        actor=master,
    )

    XPLedger.objects.create(
        user=technician,
        amount=7,
        entry_type=XPLedgerEntryType.TICKET_BASE_XP,
        reference=f"test_analytics_xp:{ticket_first_pass.id}",
    )
    XPLedger.objects.create(
        user=technician,
        amount=5,
        entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS,
        reference=f"test_analytics_xp:{ticket_rework.id}",
    )
    AttendanceRecord.objects.create(
        user=technician,
        work_date=now.date(),
        check_in_at=now,
        check_out_at=now + timedelta(hours=8),
    )

    client = authed_client_factory(analytics_users["ops"])
    resp = client.get(TEAM_URL, {"days": 7})

    assert resp.status_code == 200
    data = resp.data["data"]
    assert data["summary"]["technicians_total"] == 1
    assert data["summary"]["tickets_done_total"] == 2
    assert data["summary"]["raw_xp_total"] == 12
    member = data["members"][0]
    assert member["user_id"] == technician.id
    assert member["tickets_done"] == 2
    assert member["tickets_first_pass"] == 1
    assert member["first_pass_rate_percent"] == 50.0
    assert member["raw_xp"] == 12
    assert member["attendance_days"] == 1


def test_team_analytics_rejects_invalid_days_query(
    authed_client_factory, analytics_users
):
    client = authed_client_factory(analytics_users["ops"])

    resp = client.get(TEAM_URL, {"days": 0})

    assert resp.status_code == 400
    assert "days" in resp.data["message"].lower()
