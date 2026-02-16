import pytest
from django.utils import timezone

from core.utils.constants import (
    RoleSlug,
    TicketStatus,
    TicketTransitionAction,
    WorkSessionStatus,
    XPTransactionEntryType,
)
from gamification.models import XPTransaction
from ticket.models import TicketTransition, WorkSession
from ticket.services_workflow import TicketWorkflowService

pytestmark = pytest.mark.django_db


@pytest.fixture
def xp_ticket_context(
    user_factory, assign_roles, inventory_item_factory, ticket_factory
):
    technician = user_factory(
        username="xp_tech",
        first_name="XP Tech",
    )
    assign_roles(technician, RoleSlug.TECHNICIAN)

    master = user_factory(
        username="xp_master",
        first_name="XP Master",
    )
    qc = user_factory(
        username="xp_qc",
        first_name="XP QC",
    )
    assign_roles(qc, RoleSlug.QC_INSPECTOR)
    inventory_item = inventory_item_factory(serial_number="RM-XP-0001")

    def _make_waiting_qc_ticket(
        srt_minutes: int = 45, worked_minutes: int | None = None
    ):
        ticket = ticket_factory(
            inventory_item=inventory_item,
            master=master,
            technician=technician,
            status=TicketStatus.WAITING_QC,
            total_duration=srt_minutes,
            title="XP ticket",
        )
        if worked_minutes is not None:
            now_dt = timezone.now()
            WorkSession.objects.create(
                ticket=ticket,
                technician=technician,
                status=WorkSessionStatus.STOPPED,
                started_at=now_dt,
                ended_at=now_dt,
                last_started_at=None,
                active_seconds=max(int(worked_minutes), 0) * 60,
            )
        return ticket

    return {
        "technician": technician,
        "master": master,
        "qc": qc,
        "make_waiting_qc_ticket": _make_waiting_qc_ticket,
    }


def test_qc_pass_awards_base_and_first_pass_bonus(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](45, worked_minutes=45)

    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["qc"].id
    )

    entries = XPTransaction.objects.filter(
        user=xp_ticket_context["technician"]
    ).order_by("entry_type")
    assert entries.count() == 2
    base = entries.filter(entry_type=XPTransactionEntryType.TICKET_BASE_XP).first()
    bonus = entries.filter(
        entry_type=XPTransactionEntryType.TICKET_QC_FIRST_PASS_BONUS
    ).first()
    assert base is not None
    assert bonus is not None
    assert base.amount == 3  # ceil(45 / 20) = 3
    assert bonus.amount == 1
    checker_entry = XPTransaction.objects.get(
        reference__startswith=f"ticket_qc_status_update:{ticket.id}:"
    )
    assert checker_entry.user_id == xp_ticket_context["qc"].id
    assert checker_entry.entry_type == XPTransactionEntryType.TICKET_QC_STATUS_UPDATE
    assert checker_entry.amount == 1
    assert checker_entry.payload["qc_action"] == TicketTransitionAction.QC_PASS


def test_qc_pass_after_rework_awards_base_without_first_pass_bonus(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](21, worked_minutes=21)
    TicketWorkflowService.qc_fail_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["qc"].id
    )

    ticket.status = TicketStatus.WAITING_QC
    ticket.save(update_fields=["status"])
    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["qc"].id
    )

    entries = XPTransaction.objects.filter(user=xp_ticket_context["technician"])
    assert entries.filter(entry_type=XPTransactionEntryType.TICKET_BASE_XP).count() == 1
    assert (
        entries.filter(
            entry_type=XPTransactionEntryType.TICKET_QC_FIRST_PASS_BONUS
        ).count()
        == 0
    )
    assert (
        entries.get(entry_type=XPTransactionEntryType.TICKET_BASE_XP).amount == 2
    )  # ceil(21 / 20)
    checker_entries = XPTransaction.objects.filter(
        user=xp_ticket_context["qc"],
        entry_type=XPTransactionEntryType.TICKET_QC_STATUS_UPDATE,
    )
    assert checker_entries.count() == 2
    assert {entry.payload["qc_action"] for entry in checker_entries} == {
        TicketTransitionAction.QC_FAIL,
        TicketTransitionAction.QC_PASS,
    }


def test_qc_pass_without_rework_but_over_duration_skips_first_pass_bonus(
    xp_ticket_context,
):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](30, worked_minutes=31)

    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["qc"].id
    )

    entries = XPTransaction.objects.filter(user=xp_ticket_context["technician"])
    assert entries.filter(entry_type=XPTransactionEntryType.TICKET_BASE_XP).count() == 1
    assert (
        entries.filter(
            entry_type=XPTransactionEntryType.TICKET_QC_FIRST_PASS_BONUS
        ).count()
        == 0
    )


def test_qc_pass_logs_transition_and_creates_base_reference(xp_ticket_context):
    ticket = xp_ticket_context["make_waiting_qc_ticket"](40, worked_minutes=40)
    TicketWorkflowService.qc_pass_ticket(
        ticket=ticket, actor_user_id=xp_ticket_context["qc"].id
    )

    assert TicketTransition.objects.filter(
        ticket=ticket,
        action=TicketTransitionAction.QC_PASS,
    ).exists()
    assert (
        XPTransaction.objects.filter(reference=f"ticket_base_xp:{ticket.id}").count()
        == 1
    )
