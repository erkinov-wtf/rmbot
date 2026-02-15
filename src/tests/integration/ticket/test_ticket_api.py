import pytest

from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from ticket.models import Ticket, TicketTransition

pytestmark = pytest.mark.django_db


CREATE_URL = "/api/v1/tickets/create/"
VALID_CHECKLIST = [f"Task {idx}" for idx in range(1, 11)]


@pytest.fixture
def ticket_api_context(user_factory, assign_roles, inventory_item_factory):
    master_user = user_factory(
        username="master_api",
        first_name="Master",
        email="master_api@example.com",
    )
    assign_roles(master_user, RoleSlug.MASTER)

    regular_user = user_factory(
        username="regular_api",
        first_name="Regular",
        email="regular_api@example.com",
    )
    technician = user_factory(
        username="tech_api",
        first_name="Tech",
        email="tech_api@example.com",
    )
    inventory_item = inventory_item_factory(serial_number="RM-0100")
    return {
        "master_user": master_user,
        "regular_user": regular_user,
        "technician": technician,
        "inventory_item": inventory_item,
    }


def test_ticket_create_requires_master_role(authed_client_factory, ticket_api_context):
    client = authed_client_factory(ticket_api_context["regular_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": ticket_api_context["inventory_item"].serial_number,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 40,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 403


def test_master_can_create_ticket(authed_client_factory, ticket_api_context):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": ticket_api_context["inventory_item"].serial_number,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 40,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 201
    payload = resp.data["data"]
    assert payload["master"] == ticket_api_context["master_user"].id
    assert payload["status"] == TicketStatus.NEW
    assert payload["inventory_item"] == ticket_api_context["inventory_item"].id
    assert len(payload["checklist_snapshot"]) == 10
    assert payload["srt_approved_by"] == ticket_api_context["master_user"].id
    assert payload["srt_approved_at"] is not None
    assert Ticket.objects.count() == 1
    transition = TicketTransition.objects.get(ticket_id=payload["id"])
    assert transition.action == TicketTransitionAction.CREATED
    assert transition.actor_id == ticket_api_context["master_user"].id
    assert (
        transition.metadata["serial_number"]
        == ticket_api_context["inventory_item"].serial_number
    )
    assert transition.metadata["inventory_item_created_during_intake"] is False
    assert transition.metadata["checklist_items_count"] == 10
    assert transition.metadata["srt_approved"] is True


def test_rejects_second_active_ticket_for_same_inventory_item(
    authed_client_factory, ticket_api_context
):
    Ticket.objects.create(
        inventory_item=ticket_api_context["inventory_item"],
        master=ticket_api_context["master_user"],
        status=TicketStatus.NEW,
        title="Existing active ticket",
    )
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": ticket_api_context["inventory_item"].serial_number,
            "technician": ticket_api_context["technician"].id,
            "title": "Second ticket attempt",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 30,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "inventory item" in resp.data["message"].lower()


def test_ticket_create_rejects_short_checklist(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": ticket_api_context["inventory_item"].serial_number,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST[:5],
            "srt_total_minutes": 40,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "at least 10" in resp.data["message"].lower()


def test_ticket_create_rejects_unapproved_srt(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": ticket_api_context["inventory_item"].serial_number,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 40,
            "approve_srt": False,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "approved by master" in resp.data["message"].lower()


def test_ticket_create_requires_confirm_create_for_unknown_inventory_item(
    authed_client_factory, ticket_api_context, inventory_item_factory
):
    inventory_item_factory(serial_number="RM-0101")
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": "RM-0109",
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "confirm_create_inventory_item" in resp.data["message"]
    assert "closest matches" in resp.data["message"].lower()


def test_ticket_create_confirm_create_requires_reason(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": "RM-0999",
            "confirm_create_inventory_item": True,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "inventory_item_creation_reason" in resp.data["message"]


def test_ticket_create_confirm_create_builds_new_inventory_item_and_logs_reason(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])
    reason = "Manual intake confirmed after physical serial verification."

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": "RM-0999",
            "confirm_create_inventory_item": True,
            "inventory_item_creation_reason": reason,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 201
    payload = resp.data["data"]
    created_ticket = Ticket.objects.get(pk=payload["id"])
    assert created_ticket.inventory_item.serial_number == "RM-0999"
    transition = TicketTransition.objects.get(ticket_id=payload["id"])
    assert transition.metadata["inventory_item_created_during_intake"] is True
    assert transition.metadata["inventory_item_creation_reason"] == reason


def test_ticket_create_confirm_create_rejects_archived_inventory_item(
    authed_client_factory, ticket_api_context, inventory_item_factory
):
    archived_inventory_item = inventory_item_factory(serial_number="RM-0998")
    archived_inventory_item.delete()
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "serial_number": "RM-0998",
            "confirm_create_inventory_item": True,
            "inventory_item_creation_reason": "Trying to recreate archived inventory item.",
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "archived" in resp.data["message"].lower()
