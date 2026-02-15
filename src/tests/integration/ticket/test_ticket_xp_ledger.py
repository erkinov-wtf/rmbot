import pytest

from core.utils.constants import (
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
    XPLedgerEntryType,
)
from gamification.models import XPLedger
from ticket.models import TicketTransition
from ticket.services_workflow import TicketWorkflowService

pytestmark = pytest.mark.django_db


@pytest.fixture
def xp_ticket_context(
    user_factory, assign_roles, inventory_item_factory, ticket_factory
):
    technician = user_factory(
        username="xp_tech",
        first_name="XP Tech",
        email="xp_tech@example.com",
    )
    assign_roles(technician, RoleSlug.TECHNICIAN)

    master = user_factory(
        username="xp_master",
        first_name="XP Master",
        email="xp_master@example.com",
    )
    inventory_item = inventory_item_factory(serial_number="RM-XP-0001")

    def _make_waiting_qc_ticket(srt_minutes: int = 45):
        return ticket_factory(
            inventory_item=inventory_item,
            master=master,
            technician=technician,
            status=TicketStatus.WAITING_QC,
            total_duration=srt_minutes,
            title="XP ticket",
        )

    return {
        "technician": technician,
        "master": master,
        "make_waiting_qc_ticket": _make_waiting_qc_ticket,
    }


def test_qc_pass_awards_base_and_first_pass_bonus(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](45)

    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["master"].id
    )

    entries = XPLedger.objects.filter(user=xp_ticket_context["technician"]).order_by(
        "entry_type"
    )
    assert entries.count() == 2
    base = entries.filter(entry_type=XPLedgerEntryType.TICKET_BASE_XP).first()
    bonus = entries.filter(
        entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS
    ).first()
    assert base is not None
    assert bonus is not None
    assert base.amount == 3  # ceil(45 / 20) = 3
    assert bonus.amount == 1


def test_qc_pass_after_rework_awards_base_without_first_pass_bonus(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](21)
    TicketWorkflowService.qc_fail_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["master"].id
    )

    ticket.status = TicketStatus.WAITING_QC
    ticket.save(update_fields=["status"])
    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["master"].id
    )

    entries = XPLedger.objects.filter(user=xp_ticket_context["technician"])
    assert entries.filter(entry_type=XPLedgerEntryType.TICKET_BASE_XP).count() == 1
    assert (
        entries.filter(entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS).count()
        == 0
    )
    assert (
        entries.get(entry_type=XPLedgerEntryType.TICKET_BASE_XP).amount == 2
    )  # ceil(21 / 20)


def test_qc_pass_logs_transition_and_creates_base_reference(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](40)
    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["master"].id
    )

    assert TicketTransition.objects.filter(
        ticket=ticket,
        action=TicketTransitionAction.QC_PASS,
    ).exists()
    assert XPLedger.objects.filter(reference=f"ticket_base_xp:{ticket.id}").count() == 1
