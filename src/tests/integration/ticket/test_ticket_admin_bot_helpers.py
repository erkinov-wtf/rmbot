import pytest

from bot.services.ticket_admin_support import (
    _approve_and_assign_ticket,
    _create_ticket_from_payload,
    _set_ticket_manual_metrics,
)
from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction
from inventory.models import InventoryItemPart
from ticket.models import TicketTransition

pytestmark = pytest.mark.django_db


@pytest.fixture
def ticket_admin_bot_context(
    user_factory,
    assign_roles,
    inventory_item_factory,
):
    master = user_factory(username="bot_master", first_name="Master")
    ops = user_factory(username="bot_ops", first_name="Ops")
    technician = user_factory(username="bot_tech", first_name="Tech")
    regular_user = user_factory(username="bot_regular", first_name="Regular")

    assign_roles(master, RoleSlug.MASTER)
    assign_roles(ops, RoleSlug.OPS_MANAGER)
    assign_roles(technician, RoleSlug.TECHNICIAN)

    inventory_item = inventory_item_factory(serial_number="RM-BOT-0001")
    part_a = InventoryItemPart.objects.create(
        name="BOT-PART-A",
        category=inventory_item.category,
        inventory_item=inventory_item,
    )
    part_b = InventoryItemPart.objects.create(
        name="BOT-PART-B",
        category=inventory_item.category,
        inventory_item=inventory_item,
    )

    return {
        "master": master,
        "ops": ops,
        "technician": technician,
        "regular_user": regular_user,
        "inventory_item": inventory_item,
        "part_a": part_a,
        "part_b": part_b,
    }


def test_bot_helper_creates_ticket_with_created_transition(ticket_admin_bot_context):
    context = ticket_admin_bot_context

    ticket = _create_ticket_from_payload(
        actor_user=context["master"],
        serial_number=context["inventory_item"].serial_number,
        title="Bot Intake Ticket",
        part_specs=[
            {
                "part_id": context["part_a"].id,
                "color": "green",
                "minutes": 20,
                "comment": "Inspect",
            },
            {
                "part_id": context["part_b"].id,
                "color": "yellow",
                "minutes": 25,
                "comment": "Fix",
            },
        ],
    )

    assert ticket.status == TicketStatus.UNDER_REVIEW
    assert ticket.master_id == context["master"].id
    assert ticket.total_duration == 45
    assert TicketTransition.objects.filter(
        ticket=ticket,
        action=TicketTransitionAction.CREATED,
    ).exists()


def test_bot_helper_approve_and_assign(ticket_admin_bot_context, ticket_factory):
    context = ticket_admin_bot_context
    ticket = ticket_factory(
        inventory_item=context["inventory_item"],
        master=context["master"],
        status=TicketStatus.UNDER_REVIEW,
        title="Review Ticket",
    )

    updated = _approve_and_assign_ticket(
        ticket_id=ticket.id,
        technician_id=context["technician"].id,
        actor_user_id=context["ops"].id,
    )

    assert updated.status == TicketStatus.ASSIGNED
    assert updated.technician_id == context["technician"].id
    assert updated.approved_by_id == context["ops"].id
    assert updated.approved_at is not None


def test_bot_helper_assign_rejects_non_technician_user(
    ticket_admin_bot_context,
    ticket_factory,
):
    context = ticket_admin_bot_context
    ticket = ticket_factory(
        inventory_item=context["inventory_item"],
        master=context["master"],
        status=TicketStatus.NEW,
        title="Review Ticket",
    )

    with pytest.raises(ValueError, match="TECHNICIAN"):
        _approve_and_assign_ticket(
            ticket_id=ticket.id,
            technician_id=context["regular_user"].id,
            actor_user_id=context["ops"].id,
        )


def test_bot_helper_assign_skips_review_step_for_assigned_status(
    ticket_admin_bot_context, ticket_factory
):
    context = ticket_admin_bot_context
    ticket = ticket_factory(
        inventory_item=context["inventory_item"],
        master=context["master"],
        status=TicketStatus.ASSIGNED,
        approved_by=None,
        approved_at=None,
        title="Already assigned state",
    )

    updated = _approve_and_assign_ticket(
        ticket_id=ticket.id,
        technician_id=context["technician"].id,
        actor_user_id=context["ops"].id,
    )

    assert updated.status == TicketStatus.ASSIGNED
    assert updated.technician_id == context["technician"].id


def test_bot_helper_sets_manual_metrics(ticket_admin_bot_context, ticket_factory):
    context = ticket_admin_bot_context
    ticket = ticket_factory(
        inventory_item=context["inventory_item"],
        master=context["master"],
        status=TicketStatus.UNDER_REVIEW,
        title="Manual metrics",
        flag_color="green",
        xp_amount=2,
        is_manual=False,
    )

    updated = _set_ticket_manual_metrics(
        ticket_id=ticket.id,
        flag_color="red",
        xp_amount=55,
    )

    assert updated.flag_color == "red"
    assert updated.xp_amount == 55
    assert updated.is_manual is True
