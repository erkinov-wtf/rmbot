import pytest

from bot.services.technician_ticket_actions import TechnicianTicketActionService
from core.utils.constants import (
    RoleSlug,
    TicketStatus,
    WorkSessionStatus,
    XPTransactionEntryType,
)
from gamification.models import XPTransaction
from ticket.models import WorkSession

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
        total_duration=40,
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
    assert initial_state.potential_xp == 2
    assert initial_state.acquired_xp == 0
    assert initial_state.actions == (TechnicianTicketActionService.ACTION_START,)
    state_text = TechnicianTicketActionService.render_state_message(
        state=initial_state,
        heading="Ticket details",
    )
    assert "Potential XP: +2" in state_text
    assert "Acquired XP: +0" in state_text
    assert "XP progress: 0/2" in state_text

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


def test_queue_callback_data_roundtrip(technician_ticket_context):
    ticket = technician_ticket_context["ticket"]
    open_payload = TechnicianTicketActionService.build_queue_callback_data(
        action=TechnicianTicketActionService.QUEUE_ACTION_OPEN,
        ticket_id=ticket.id,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
    )
    refresh_payload = TechnicianTicketActionService.build_queue_callback_data(
        action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
    )

    assert TechnicianTicketActionService.parse_queue_callback_data(
        callback_data=open_payload
    ) == (
        TechnicianTicketActionService.QUEUE_ACTION_OPEN,
        ticket.id,
        TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        1,
    )
    assert TechnicianTicketActionService.parse_queue_callback_data(
        callback_data=refresh_payload
    ) == (
        TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
        None,
        TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        1,
    )
    assert TechnicianTicketActionService.parse_queue_callback_data(
        callback_data=f"{TechnicianTicketActionService.QUEUE_CALLBACK_PREFIX}:refresh"
    ) == (
        TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
        None,
        TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        1,
    )
    assert TechnicianTicketActionService.parse_queue_callback_data(
        callback_data=f"{TechnicianTicketActionService.QUEUE_CALLBACK_PREFIX}:open:{ticket.id}"
    ) == (
        TechnicianTicketActionService.QUEUE_ACTION_OPEN,
        ticket.id,
        TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
        1,
    )
    assert (
        TechnicianTicketActionService.parse_queue_callback_data(
            callback_data="invalid:data"
        )
        is None
    )


def test_queue_keyboard_renders_ticket_buttons_and_pagination(
    technician_ticket_context,
):
    ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]
    states = TechnicianTicketActionService.queue_states_for_technician(
        technician_id=technician.id
    )

    markup = TechnicianTicketActionService.build_queue_keyboard(states=states)
    assert markup is not None
    assert markup.inline_keyboard[0][0].callback_data == (
        TechnicianTicketActionService.build_queue_callback_data(
            action=TechnicianTicketActionService.QUEUE_ACTION_OPEN,
            ticket_id=ticket.id,
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            page=1,
        )
    )
    assert [button.text for button in markup.inline_keyboard[-1]] == ["<", "1/1", ">"]
    assert markup.inline_keyboard[-1][0].callback_data == (
        TechnicianTicketActionService.build_queue_callback_data(
            action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            page=1,
        )
    )
    assert markup.inline_keyboard[-1][1].callback_data == (
        TechnicianTicketActionService.build_queue_callback_data(
            action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            page=1,
        )
    )
    assert markup.inline_keyboard[-1][2].callback_data == (
        TechnicianTicketActionService.build_queue_callback_data(
            action=TechnicianTicketActionService.QUEUE_ACTION_REFRESH,
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            page=1,
        )
    )


def test_view_states_for_under_qc_and_past_scopes(
    technician_ticket_context,
    ticket_factory,
    inventory_item_factory,
):
    assigned_ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]

    waiting_qc_ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-TG-0101"),
        master=assigned_ticket.master,
        technician=technician,
        status=TicketStatus.WAITING_QC,
    )
    done_ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-TG-0102"),
        master=assigned_ticket.master,
        technician=technician,
        status=TicketStatus.DONE,
    )

    under_qc_states = TechnicianTicketActionService.view_states_for_technician(
        technician_id=technician.id,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
    )
    past_states = TechnicianTicketActionService.view_states_for_technician(
        technician_id=technician.id,
        scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
    )
    active_states = TechnicianTicketActionService.view_states_for_technician(
        technician_id=technician.id,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
    )

    assert [state.ticket_id for state in under_qc_states] == [waiting_qc_ticket.id]
    assert [state.ticket_id for state in past_states] == [done_ticket.id]
    assert [state.ticket_id for state in active_states] == [assigned_ticket.id]

    under_qc_summary = TechnicianTicketActionService.render_queue_summary(
        states=under_qc_states,
        scope=TechnicianTicketActionService.VIEW_SCOPE_UNDER_QC,
    )
    past_summary = TechnicianTicketActionService.render_queue_summary(
        states=past_states,
        scope=TechnicianTicketActionService.VIEW_SCOPE_PAST,
    )
    active_summary = TechnicianTicketActionService.render_queue_summary(
        states=active_states,
        scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
    )

    assert "Total waiting QC tickets: 1" in under_qc_summary
    assert "Total past tickets: 1" in past_summary
    assert "Total active tickets: 1" in active_summary


def test_paginated_view_states_clamps_out_of_bounds_page(
    technician_ticket_context,
    ticket_factory,
    inventory_item_factory,
):
    assigned_ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]

    for index in range(6):
        ticket_factory(
            inventory_item=inventory_item_factory(
                serial_number=f"RM-TG-PAGE-{index + 1:02d}"
            ),
            master=assigned_ticket.master,
            technician=technician,
            status=TicketStatus.ASSIGNED,
        )

    states, safe_page, page_count, total_count = (
        TechnicianTicketActionService.paginated_view_states_for_technician(
            technician_id=technician.id,
            scope=TechnicianTicketActionService.VIEW_SCOPE_ACTIVE,
            page=99,
            per_page=5,
        )
    )

    assert total_count == 7
    assert page_count == 2
    assert safe_page == 2
    assert len(states) == 2


def test_state_includes_acquired_xp_for_ticket(technician_ticket_context):
    ticket = technician_ticket_context["ticket"]
    technician = technician_ticket_context["technician"]

    XPTransaction.objects.create(
        user=technician,
        amount=3,
        entry_type=XPTransactionEntryType.TICKET_BASE_XP,
        reference=f"test_ticket_base:{ticket.id}",
        payload={"ticket_id": ticket.id},
    )

    state = TechnicianTicketActionService.state_for_ticket(
        ticket=ticket,
        technician_id=technician.id,
    )
    assert state.acquired_xp == 3
