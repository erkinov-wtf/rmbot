from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import Role, User
from attendance.models import AttendanceRecord
from bike.models import Bike
from core.utils.constants import RoleSlug, TicketStatus, TicketTransitionAction, XPLedgerEntryType
from gamification.models import XPLedger
from ticket.models import Ticket, TicketTransition


class AuditFeedAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/misc/audit-feed/"

        self.ops = User.objects.create_user(
            username="audit_ops",
            password="pass1234",
            first_name="Ops",
            email="audit_ops@example.com",
        )
        self.regular = User.objects.create_user(
            username="audit_regular",
            password="pass1234",
            first_name="Regular",
            email="audit_regular@example.com",
        )
        ops_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.OPS_MANAGER,
            defaults={"name": "Ops Manager"},
        )
        self.ops.roles.add(ops_role)

        bike = Bike.objects.create(bike_code="RM-AUD-0001")
        ticket = Ticket.objects.create(
            bike=bike,
            master=self.ops,
            technician=self.ops,
            status=TicketStatus.DONE,
            title="Audit ticket",
        )
        TicketTransition.objects.create(
            ticket=ticket,
            from_status=TicketStatus.WAITING_QC,
            to_status=TicketStatus.DONE,
            action=TicketTransitionAction.QC_PASS,
            actor=self.ops,
        )
        XPLedger.objects.create(
            user=self.ops,
            amount=2,
            entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
            reference="audit_feed_test_xp",
            payload={},
        )
        AttendanceRecord.objects.create(
            user=self.ops,
            work_date=timezone.localdate(),
            check_in_at=timezone.now(),
        )

    def test_requires_ops_or_super_admin(self):
        self.client.force_authenticate(user=self.regular)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_returns_mixed_event_feed(self):
        self.client.force_authenticate(user=self.ops)
        resp = self.client.get(f"{self.url}?limit=20")
        self.assertEqual(resp.status_code, 200)
        feed = resp.data["data"]
        self.assertGreaterEqual(len(feed), 3)

        event_types = {event["event_type"] for event in feed}
        self.assertIn("ticket_transition", event_types)
        self.assertIn("xp_ledger", event_types)
        self.assertIn("attendance_check_in", event_types)

    def test_limit_and_validation(self):
        self.client.force_authenticate(user=self.ops)
        invalid = self.client.get(f"{self.url}?limit=abc")
        self.assertEqual(invalid.status_code, 400)
        self.assertFalse(invalid.data["success"])

        limited = self.client.get(f"{self.url}?limit=1")
        self.assertEqual(limited.status_code, 200)
        self.assertEqual(len(limited.data["data"]), 1)
