import pytest

from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from inventory.models import InventoryItemPart
from ticket.models import Ticket, TicketTransition

pytestmark = pytest.mark.django_db


CREATE_URL = "/api/v1/tickets/create/"


def _payload(context: dict, **overrides):
    payload = {
        "serial_number": context["inventory_item"].serial_number,
        "title": "Diagnostics",
        "part_specs": [
            {
                "part_id": context["part_a"].id,
                "color": "green",
                "comment": "Inspect part A",
                "minutes": 20,
            },
            {
                "part_id": context["part_b"].id,
                "color": "yellow",
                "comment": "Fix part B",
                "minutes": 25,
            },
        ],
    }
    payload.update(overrides)
    return payload


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

    inventory_item = inventory_item_factory(serial_number="RM-0100")
    part_a = InventoryItemPart.objects.create(name="RM-API-PART-A")
    part_b = InventoryItemPart.objects.create(name="RM-API-PART-B")
    inventory_item.parts.set([part_a, part_b])

    return {
        "master_user": master_user,
        "regular_user": regular_user,
        "inventory_item": inventory_item,
        "part_a": part_a,
        "part_b": part_b,
    }


def test_ticket_create_requires_master_role(authed_client_factory, ticket_api_context):
    client = authed_client_factory(ticket_api_context["regular_user"])

    resp = client.post(CREATE_URL, _payload(ticket_api_context), format="json")

    assert resp.status_code == 403


def test_master_can_create_ticket_with_auto_metrics(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(CREATE_URL, _payload(ticket_api_context), format="json")

    assert resp.status_code == 201
    payload = resp.data["data"]
    assert payload["master"] == ticket_api_context["master_user"].id
    assert payload["status"] == TicketStatus.UNDER_REVIEW
    assert payload["technician"] is None
    assert payload["inventory_item"] == ticket_api_context["inventory_item"].id
    assert payload["total_duration"] == 45
    assert payload["flag_minutes"] == 45
    assert payload["flag_color"] == "yellow"
    assert payload["xp_amount"] == 3
    assert payload["is_manual"] is False
    assert len(payload["ticket_parts"]) == 2
    assert Ticket.objects.count() == 1
    transition = TicketTransition.objects.get(ticket_id=payload["id"])
    assert transition.action == TicketTransitionAction.CREATED
    assert transition.actor_id == ticket_api_context["master_user"].id
    assert (
        transition.metadata["serial_number"]
        == ticket_api_context["inventory_item"].serial_number
    )
    assert transition.metadata["part_specs_count"] == 2
    assert transition.metadata["total_minutes"] == 45
    assert transition.metadata["inventory_item_created_during_intake"] is False


def test_rejects_second_active_ticket_for_same_inventory_item(
    authed_client_factory, ticket_api_context
):
    Ticket.objects.create(
        inventory_item=ticket_api_context["inventory_item"],
        master=ticket_api_context["master_user"],
        status=TicketStatus.UNDER_REVIEW,
        title="Existing active ticket",
    )
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(CREATE_URL, _payload(ticket_api_context), format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "inventory item" in resp.data["message"].lower()


def test_ticket_create_requires_part_specs(authed_client_factory, ticket_api_context):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        _payload(ticket_api_context, part_specs=[]),
        format="json",
    )

    assert resp.status_code == 400
    assert "part_specs" in resp.data["message"]


def test_ticket_create_rejects_missing_inventory_item_parts(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        _payload(
            ticket_api_context,
            part_specs=[
                {
                    "part_id": ticket_api_context["part_a"].id,
                    "color": "green",
                    "comment": "Only one part submitted",
                    "minutes": 20,
                }
            ],
        ),
        format="json",
    )

    assert resp.status_code == 400
    assert "missing required part ids" in resp.data["message"].lower()


def test_ticket_create_manual_override_sets_manual_mode(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        _payload(
            ticket_api_context,
            flag_color="red",
            xp_amount=99,
        ),
        format="json",
    )

    assert resp.status_code == 201
    payload = resp.data["data"]
    assert payload["flag_color"] == "red"
    assert payload["xp_amount"] == 99
    assert payload["is_manual"] is True


def test_ticket_create_manual_override_requires_both_fields(
    authed_client_factory, ticket_api_context
):
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        _payload(ticket_api_context, xp_amount=50),
        format="json",
    )

    assert resp.status_code == 400
    assert "manual override requires both" in resp.data["message"].lower()


def test_ticket_create_requires_confirm_create_for_unknown_inventory_item(
    authed_client_factory, ticket_api_context, inventory_item_factory
):
    inventory_item_factory(serial_number="RM-0101")
    client = authed_client_factory(ticket_api_context["master_user"])

    resp = client.post(
        CREATE_URL,
        _payload(ticket_api_context, serial_number="RM-0109"),
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
        _payload(
            ticket_api_context,
            serial_number="RM-0999",
            confirm_create_inventory_item=True,
        ),
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
        _payload(
            ticket_api_context,
            serial_number="RM-0999",
            confirm_create_inventory_item=True,
            inventory_item_creation_reason=reason,
        ),
        format="json",
    )

    assert resp.status_code == 201
    payload = resp.data["data"]
    created_ticket = Ticket.objects.get(pk=payload["id"])
    assert created_ticket.inventory_item.serial_number == "RM-0999"
    assert set(created_ticket.inventory_item.parts.values_list("id", flat=True)) == {
        ticket_api_context["part_a"].id,
        ticket_api_context["part_b"].id,
    }
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
        _payload(
            ticket_api_context,
            serial_number="RM-0998",
            confirm_create_inventory_item=True,
            inventory_item_creation_reason=(
                "Trying to recreate archived inventory item."
            ),
        ),
        format="json",
    )

    assert resp.status_code == 400
    assert "archived" in resp.data["message"].lower()
