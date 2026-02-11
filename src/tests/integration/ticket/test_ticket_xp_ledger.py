from django.test import TestCase

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction, XPLedgerEntryType
from gamification.models import XPLedger
from ticket.models import Ticket, TicketTransition
from ticket.services import qc_fail_ticket, qc_pass_ticket


class TicketXPLedgerTests(TestCase):
    def setUp(self):
        self.technician = User.objects.create_user(
            username="xp_tech",
            password="pass1234",
            first_name="XP Tech",
            email="xp_tech@example.com",
        )
        tech_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.TECHNICIAN,
            defaults={"name": "Technician"},
        )
        self.technician.roles.add(tech_role)

        self.master = User.objects.create_user(
            username="xp_master",
            password="pass1234",
            first_name="XP Master",
            email="xp_master@example.com",
        )
        self.bike = Bike.objects.create(bike_code="RM-XP-0001")

    def _make_waiting_qc_ticket(self, *, srt_minutes: int = 45) -> Ticket:
        return Ticket.objects.create(
            bike=self.bike,
            master=self.master,
            technician=self.technician,
            status=TicketStatus.WAITING_QC,
            srt_total_minutes=srt_minutes,
            title="XP ticket",
        )

    def test_qc_pass_awards_base_and_first_pass_bonus(self):
        ticket = self._make_waiting_qc_ticket(srt_minutes=45)

        qc_pass_ticket(ticket=ticket, actor_user_id=self.master.id)

        entries = XPLedger.objects.filter(user=self.technician).order_by("entry_type")
        self.assertEqual(entries.count(), 2)
        base = entries.filter(entry_type=XPLedgerEntryType.TICKET_BASE_XP).first()
        bonus = entries.filter(entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS).first()
        self.assertIsNotNone(base)
        self.assertIsNotNone(bonus)
        self.assertEqual(base.amount, 3)  # ceil(45 / 20) = 3
        self.assertEqual(bonus.amount, 1)

    def test_qc_pass_after_rework_awards_base_without_first_pass_bonus(self):
        ticket = self._make_waiting_qc_ticket(srt_minutes=21)
        qc_fail_ticket(ticket=ticket, actor_user_id=self.master.id)

        # Simulate rework completion back to waiting_qc
        ticket.status = TicketStatus.WAITING_QC
        ticket.save(update_fields=["status"])
        qc_pass_ticket(ticket=ticket, actor_user_id=self.master.id)

        entries = XPLedger.objects.filter(user=self.technician)
        self.assertEqual(entries.filter(entry_type=XPLedgerEntryType.TICKET_BASE_XP).count(), 1)
        self.assertEqual(entries.filter(entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS).count(), 0)
        self.assertEqual(entries.get(entry_type=XPLedgerEntryType.TICKET_BASE_XP).amount, 2)  # ceil(21 / 20)

    def test_qc_pass_logs_transition_and_creates_base_reference(self):
        ticket = self._make_waiting_qc_ticket(srt_minutes=40)
        qc_pass_ticket(ticket=ticket, actor_user_id=self.master.id)

        self.assertTrue(
            TicketTransition.objects.filter(
                ticket=ticket,
                action=TicketTransitionAction.QC_PASS,
            ).exists()
        )
        self.assertEqual(XPLedger.objects.filter(reference=f"ticket_base_xp:{ticket.id}").count(), 1)
