import pytest

from core.utils.constants import RoleSlug, TicketStatus, WorkSessionStatus
from ticket.models import WorkSession
from ticket.services_technician_actions import TechnicianTicketActionService

pytestmark = pytest.mark.django_db


@pytest.fixture
def technician_ticket_context(
    user_factory,
    assign_roles,
    inventory_item_factory,
    ticket_factory,
):
    master = user_factory(username="tg_master", first_name="Master")
    technician = user_factory(username="tg_tech", first_name="Tech")
    assign_roles(master, RoleSlug.MASTER)
    assign_roles(technician, RoleSlug.TECHNICIAN)

    inventory_item = inventory_item_factory(serial_number="RM-TG-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=master,
        technician=technician,
        status=TicketStatus.ASSIGNED,
    )
    return {
        "ticket": ticket,
        "technician": technician,
    }


def test_technician_action_flow_updates_available_buttons(technician_ticket_context):
    ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]

    initial_state = TechnicianTicketActionService.state_for_ticket(
        ticket=ticket,
        technician_id=technician.id,
    )
    assert initial_state.actions == (TechnicianTicketActionService.ACTION_START,)
    initial_keyboard = TechnicianTicketActionService.build_action_keyboard(
        ticket_id=ticket.id,
        actions=initial_state.actions,
    )
    assert initial_keyboard is not None
    assert initial_keyboard.inline_keyboard[0][0].callback_data == (
        TechnicianTicketActionService.build_callback_data(
            ticket_id=ticket.id,
            action=TechnicianTicketActionService.ACTION_START,
        )
    )

    started_state = TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_START,
    )
    assert started_state.ticket_status == TicketStatus.IN_PROGRESS
    assert set(started_state.actions) == {
        TechnicianTicketActionService.ACTION_PAUSE,
        TechnicianTicketActionService.ACTION_STOP,
    }
    assert (
        WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician.id,
        ).status
        == WorkSessionStatus.RUNNING
    )

    paused_state = TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_PAUSE,
    )
    assert set(paused_state.actions) == {
        TechnicianTicketActionService.ACTION_RESUME,
        TechnicianTicketActionService.ACTION_STOP,
    }
    assert (
        WorkSession.domain.get_open_for_ticket_and_technician(
            ticket=ticket,
            technician_id=technician.id,
        ).status
        == WorkSessionStatus.PAUSED
    )

    resumed_state = TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_RESUME,
    )
    assert set(resumed_state.actions) == {
        TechnicianTicketActionService.ACTION_PAUSE,
        TechnicianTicketActionService.ACTION_STOP,
    }

    stopped_state = TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_STOP,
    )
    assert stopped_state.actions == (
        TechnicianTicketActionService.ACTION_TO_WAITING_QC,
    )

    to_qc_state = TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_TO_WAITING_QC,
    )
    assert to_qc_state.ticket_status == TicketStatus.WAITING_QC
    assert to_qc_state.actions == ()
    assert (
        TechnicianTicketActionService.build_action_keyboard(
            ticket_id=ticket.id,
            actions=to_qc_state.actions,
        )
        is None
    )


def test_start_action_is_blocked_on_other_tickets_while_session_is_open(
    technician_ticket_context,
    ticket_factory,
    inventory_item_factory,
):
    primary_ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]
    secondary_ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-TG-0002"),
        master=primary_ticket.master,
        technician=technician,
        status=TicketStatus.ASSIGNED,
    )

    TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=primary_ticket.id,
        action=TechnicianTicketActionService.ACTION_START,
    )
    blocked_state = TechnicianTicketActionService.state_for_ticket(
        ticket=secondary_ticket,
        technician_id=technician.id,
    )
    assert blocked_state.actions == ()

    TechnicianTicketActionService.execute_for_technician(
        technician_id=technician.id,
        ticket_id=primary_ticket.id,
        action=TechnicianTicketActionService.ACTION_STOP,
    )
    unblocked_state = TechnicianTicketActionService.state_for_ticket(
        ticket=secondary_ticket,
        technician_id=technician.id,
    )
    assert unblocked_state.actions == (TechnicianTicketActionService.ACTION_START,)


def test_technician_action_service_rejects_unavailable_action(
    technician_ticket_context,
):
    ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]

    with pytest.raises(ValueError, match="not available"):
        TechnicianTicketActionService.execute_for_technician(
            technician_id=technician.id,
            ticket_id=ticket.id,
            action=TechnicianTicketActionService.ACTION_PAUSE,
        )


def test_callback_data_roundtrip(technician_ticket_context):
    ticket = technician_ticket_context["ticket"]

    payload = TechnicianTicketActionService.build_callback_data(
        ticket_id=ticket.id,
        action=TechnicianTicketActionService.ACTION_STOP,
    )
    assert TechnicianTicketActionService.parse_callback_data(callback_data=payload) == (
        ticket.id,
        TechnicianTicketActionService.ACTION_STOP,
    )
    assert (
        TechnicianTicketActionService.parse_callback_data(callback_data="invalid:data")
        is None
    )
