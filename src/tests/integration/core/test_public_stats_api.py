from datetime import timedelta

import pytest
from django.utils import timezone

from attendance.models import AttendanceRecord
from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from gamification.models import XPTransaction
from inventory.models import InventoryItemStatus
from ticket.models import Ticket, TicketTransition

pytestmark = pytest.mark.django_db

LEADERBOARD_URL = "/api/v1/analytics/public/leaderboard/"


@pytest.fixture
def public_stats_context(user_factory, assign_roles, inventory_item_factory):
    master = user_factory(username="public_stats_master", first_name="Master")
    assign_roles(master, RoleSlug.MASTER)

    tech_top = user_factory(username="public_stats_top", first_name="Top")
    assign_roles(tech_top, RoleSlug.TECHNICIAN)

    tech_second = user_factory(username="public_stats_second", first_name="Second")
    assign_roles(tech_second, RoleSlug.TECHNICIAN)

    user_factory(username="public_stats_regular", first_name="Regular")

    now = timezone.now()

    top_ticket_green = Ticket.objects.create(
        inventory_item=inventory_item_factory(
            serial_number="RM-PS-0001", status=InventoryItemStatus.READY
        ),
        master=master,
        technician=tech_top,
        status=TicketStatus.DONE,
        title="Top Green",
        flag_color="green",
        total_duration=20,
        finished_at=now - timedelta(days=2),
    )
    top_ticket_yellow = Ticket.objects.create(
        inventory_item=inventory_item_factory(
            serial_number="RM-PS-0002", status=InventoryItemStatus.READY
        ),
        master=master,
        technician=tech_top,
        status=TicketStatus.DONE,
        title="Top Yellow",
        flag_color="yellow",
        total_duration=45,
        finished_at=now - timedelta(days=1),
    )
    top_ticket_red = Ticket.objects.create(
        inventory_item=inventory_item_factory(
            serial_number="RM-PS-0003", status=InventoryItemStatus.READY
        ),
        master=master,
        technician=tech_top,
        status=TicketStatus.DONE,
        title="Top Red",
        flag_color="red",
        total_duration=90,
        finished_at=now,
    )

    second_ticket_1 = Ticket.objects.create(
        inventory_item=inventory_item_factory(
            serial_number="RM-PS-0004", status=InventoryItemStatus.READY
        ),
        master=master,
        technician=tech_second,
        status=TicketStatus.DONE,
        title="Second One",
        flag_color="green",
        total_duration=25,
        finished_at=now - timedelta(days=1),
    )
    second_ticket_2 = Ticket.objects.create(
        inventory_item=inventory_item_factory(
            serial_number="RM-PS-0005", status=InventoryItemStatus.READY
        ),
        master=master,
        technician=tech_second,
        status=TicketStatus.DONE,
        title="Second Two",
        flag_color="green",
        total_duration=30,
        finished_at=now,
    )

    TicketTransition.objects.create(
        ticket=top_ticket_red,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.REWORK,
        action=TicketTransitionAction.QC_FAIL,
        actor=master,
    )
    TicketTransition.objects.create(
        ticket=top_ticket_red,
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=master,
    )

    XPTransaction.objects.create(
        user=tech_top,
        amount=40,
        entry_type="ticket_base_xp",
        reference="public_stats_top_xp_1",
    )
    XPTransaction.objects.create(
        user=tech_second,
        amount=20,
        entry_type="ticket_base_xp",
        reference="public_stats_second_xp_1",
    )

    AttendanceRecord.objects.create(
        user=tech_top,
        work_date=(now - timedelta(days=1)).date(),
        check_in_at=now - timedelta(days=1, hours=8),
        check_out_at=now - timedelta(days=1),
    )
    AttendanceRecord.objects.create(
        user=tech_top,
        work_date=now.date(),
        check_in_at=now - timedelta(hours=8),
        check_out_at=now,
    )
    AttendanceRecord.objects.create(
        user=tech_second,
        work_date=now.date(),
        check_in_at=now - timedelta(hours=9),
        check_out_at=now - timedelta(hours=1),
    )

    return {
        "top": tech_top,
        "second": tech_second,
        "top_ticket_ids": [top_ticket_green.id, top_ticket_yellow.id, top_ticket_red.id],
        "second_ticket_ids": [second_ticket_1.id, second_ticket_2.id],
    }


def test_public_leaderboard_is_accessible_without_auth(
    api_client, public_stats_context
):
    response = api_client.get(LEADERBOARD_URL)

    assert response.status_code == 200
    data = response.data["data"]
    assert data["summary"]["technicians_total"] == 2
    assert len(data["members"]) == 2

    top_member = data["members"][0]
    assert top_member["user_id"] == public_stats_context["top"].id
    assert top_member["rank"] == 1
    assert top_member["tickets_done_total"] == 3
    assert top_member["tickets_closed_by_flag"]["green"] == 1
    assert top_member["tickets_closed_by_flag"]["yellow"] == 1
    assert top_member["tickets_closed_by_flag"]["red"] == 1
    assert "score_components" in top_member


def test_public_technician_detail_returns_full_breakdown(
    api_client, public_stats_context
):
    user_id = public_stats_context["top"].id
    response = api_client.get(f"/api/v1/analytics/public/technicians/{user_id}/")

    assert response.status_code == 200
    data = response.data["data"]
    assert data["profile"]["user_id"] == user_id
    assert data["leaderboard_position"]["rank"] == 1
    assert data["metrics"]["tickets"]["tickets_done_total"] == 3
    assert data["metrics"]["tickets"]["tickets_closed_by_flag"]["green"] == 1
    assert data["metrics"]["tickets"]["tickets_closed_by_flag"]["yellow"] == 1
    assert data["metrics"]["tickets"]["tickets_closed_by_flag"]["red"] == 1
    assert data["metrics"]["xp"]["xp_total"] == 40
    assert data["metrics"]["attendance"]["attendance_days_total"] == 2
    assert data["score_breakdown"]["reasoning"]["top_positive_factors"]
    assert data["recent"]["done_tickets"]
    assert data["recent"]["xp_transactions"]


def test_public_technician_detail_returns_404_for_unknown_technician(api_client):
    response = api_client.get("/api/v1/analytics/public/technicians/999999/")

    assert response.status_code == 404
    assert response.data["success"] is False
    assert "not found" in response.data["error"]["detail"].lower()
