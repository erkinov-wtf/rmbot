from django.core.exceptions import ValidationError
from django.test import TestCase

from account.models import User
from bike.models import Bike
from core.utils.constants import TicketStatus, TicketTransitionAction, XPLedgerEntryType
from gamification.models import XPLedger
from ticket.models import Ticket, TicketTransition


class AppendOnlyModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="append_only_user",
            password="pass1234",
            first_name="Append",
            email="append_only_user@example.com",
        )
        self.bike = Bike.objects.create(bike_code="RM-APP-0001")
        self.ticket = Ticket.objects.create(
            bike=self.bike,
            master=self.user,
            technician=self.user,
            status=TicketStatus.DONE,
            title="Append-only ticket",
        )

    def test_xp_ledger_is_append_only(self):
        entry = XPLedger.objects.create(
            user=self.user,
            amount=2,
            entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
            reference="append-only-xp-entry",
            payload={},
        )

        entry.amount = 10
        with self.assertRaises(ValidationError):
            entry.save()

        with self.assertRaises(ValidationError):
            XPLedger.objects.filter(pk=entry.pk).update(amount=99)

        with self.assertRaises(ValidationError):
            entry.delete()

        with self.assertRaises(ValidationError):
            XPLedger.objects.filter(pk=entry.pk).delete()

        self.assertEqual(XPLedger.objects.filter(pk=entry.pk).count(), 1)

    def test_ticket_transition_is_append_only(self):
        transition = TicketTransition.objects.create(
            ticket=self.ticket,
            from_status=TicketStatus.WAITING_QC,
            to_status=TicketStatus.DONE,
            action=TicketTransitionAction.QC_PASS,
            actor=self.user,
            metadata={"source": "test"},
        )

        transition.note = "mutate"
        with self.assertRaises(ValidationError):
            transition.save()

        with self.assertRaises(ValidationError):
            TicketTransition.objects.filter(pk=transition.pk).update(note="mutate")

        with self.assertRaises(ValidationError):
            transition.delete()

        with self.assertRaises(ValidationError):
            TicketTransition.objects.filter(pk=transition.pk).delete()

        self.assertEqual(TicketTransition.objects.filter(pk=transition.pk).count(), 1)
