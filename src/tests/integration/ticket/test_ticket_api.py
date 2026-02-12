import pytest

from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from ticket.models import Ticket, TicketTransition

pytestmark = pytest.mark.django_db


CREATE_URL = "/api/v1/tickets/create/"
VALID_CHECKLIST = [f"Task {idx}" for idx in range(1, 11)]


@pytest.fixture
def ticket_api_context(user_factory, assign_roles, bike_factory):
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
    bike = bike_factory(bike_code="RM-0100")
    return {
        "master_user": master_user,
        "regular_user": regular_user,
        "technician": technician,
        "bike": bike,
    }


def test_ticket_create_requires_master_role(authed_client_factory, ticket_api_context):
    client = authed_client_factory(ticket_api_context["regular_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": ticket_api_context["bike"].bike_code,
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
            "bike_code": ticket_api_context["bike"].bike_code,
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
    assert payload["bike"] == ticket_api_context["bike"].id
    assert len(payload["checklist_snapshot"]) == 10
    assert payload["srt_approved_by"] == ticket_api_context["master_user"].id
    assert payload["srt_approved_at"] is not None
    assert Ticket.objects.count() == 1
    transition = TicketTransition.objects.get(ticket_id=payload["id"])
    assert transition.action == TicketTransitionAction.CREATED
    assert transition.actor_id == ticket_api_context["master_user"].id
    assert transition.metadata["bike_code"] == ticket_api_context["bike"].bike_code
    assert transition.metadata["bike_created_during_intake"] is False
    assert transition.metadata["checklist_items_count"] == 10
    assert transition.metadata["srt_approved"] is True


def test_rejects_second_active_ticket_for_same_bike(
    authed_client_factory, ticket_api_context
):
    Ticket.objects.create(
        bike=ticket_api_context["bike"],
        master=ticket_api_context["master_user"],
        status=TicketStatus.NEW,
        title="Existing active ticket",
    )
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": ticket_api_context["bike"].bike_code,
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
    assert "bike" in resp.data["message"].lower()


def test_ticket_create_rejects_short_checklist(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": ticket_api_context["bike"].bike_code,
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
            "bike_code": ticket_api_context["bike"].bike_code,
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


def test_ticket_create_requires_confirm_create_for_unknown_bike(
    authed_client_factory, ticket_api_context, bike_factory
):
    bike_factory(bike_code="RM-0101")
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": "RM-0109",
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "confirm_create_bike" in resp.data["message"]
    assert "closest matches" in resp.data["message"].lower()


def test_ticket_create_confirm_create_requires_reason(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": "RM-0999",
            "confirm_create_bike": True,
            "technician": ticket_api_context["technician"].id,
            "title": "Diagnostics",
            "checklist_snapshot": VALID_CHECKLIST,
            "srt_total_minutes": 35,
            "approve_srt": True,
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "bike_creation_reason" in resp.data["message"]


def test_ticket_create_confirm_create_builds_new_bike_and_logs_reason(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])
    reason = "Manual intake confirmed after physical bike-code verification."

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": "RM-0999",
            "confirm_create_bike": True,
            "bike_creation_reason": reason,
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
    assert created_ticket.bike.bike_code == "RM-0999"
    transition = TicketTransition.objects.get(ticket_id=payload["id"])
    assert transition.metadata["bike_created_during_intake"] is True
    assert transition.metadata["bike_creation_reason"] == reason


def test_ticket_create_confirm_create_rejects_archived_bike_code(
    authed_client_factory, ticket_api_context, bike_factory
):
    archived_bike = bike_factory(bike_code="RM-0998")
    archived_bike.delete()
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        {
            "bike_code": "RM-0998",
            "confirm_create_bike": True,
            "bike_creation_reason": "Trying to recreate archived bike.",
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
