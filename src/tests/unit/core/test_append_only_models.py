import pytest
from django.core.exceptions import ValidationError

from core.utils.constants import (
    TicketStatus,
    TicketTransitionAction,
    XPTransactionEntryType,
)
from gamification.models import XPTransaction
from ticket.models import TicketTransition

pytestmark = pytest.mark.django_db


@pytest.fixture
def append_only_context(user_factory, inventory_item_factory, ticket_factory):
    user = user_factory(
        username="append_only_user",
        first_name="Append",
        email="append_only_user@example.com",
    )
    inventory_item = inventory_item_factory(serial_number="RM-APP-0001")
    ticket = ticket_factory(
        inventory_item=inventory_item,
        master=user,
        technician=user,
        status=TicketStatus.DONE,
        title="Append-only ticket",
    )
    return {
        "user": user,
        "ticket": ticket,
    }


def test_xp_transaction_is_append_only(append_only_context):
    entry = XPTransaction.objects.create(
        user=append_only_context["user"],
        amount=2,
        entry_type=XPTransactionEntryType.ATTENDANCE_PUNCTUALITY,
        reference="append-only-xp-entry",
        payload={},
    )

    entry.amount = 10
    with pytest.raises(ValidationError):
        entry.save()

    with pytest.raises(ValidationError):
        XPTransaction.objects.filter(pk=entry.pk).update(amount=99)

    with pytest.raises(ValidationError):
        entry.delete()

    with pytest.raises(ValidationError):
        XPTransaction.objects.filter(pk=entry.pk).delete()

    assert XPTransaction.objects.filter(pk=entry.pk).count() == 1


def test_ticket_transition_is_append_only(append_only_context):
    transition = TicketTransition.objects.create(
        ticket=append_only_context["ticket"],
        from_status=TicketStatus.WAITING_QC,
        to_status=TicketStatus.DONE,
        action=TicketTransitionAction.QC_PASS,
        actor=append_only_context["user"],
        metadata={"source": "test"},
    )

    transition.note = "mutate"
    with pytest.raises(ValidationError):
        transition.save()

    with pytest.raises(ValidationError):
        TicketTransition.objects.filter(pk=transition.pk).update(note="mutate")

    with pytest.raises(ValidationError):
        transition.delete()

    with pytest.raises(ValidationError):
        TicketTransition.objects.filter(pk=transition.pk).delete()

    assert TicketTransition.objects.filter(pk=transition.pk).count() == 1
