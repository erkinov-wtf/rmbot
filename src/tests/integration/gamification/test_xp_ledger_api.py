from django.test import TestCase
from rest_framework.test import APIClient

from account.models import Role, User
from core.utils.constants import RoleSlug, XPLedgerEntryType
from gamification.models import XPLedger


class XPLedgerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/xp/ledger/"

        self.tech_one = User.objects.create_user(
            username="xp_api_tech_one",
            password="pass1234",
            first_name="Tech One",
            email="xp_api_tech_one@example.com",
        )
        self.tech_two = User.objects.create_user(
            username="xp_api_tech_two",
            password="pass1234",
            first_name="Tech Two",
            email="xp_api_tech_two@example.com",
        )
        self.ops = User.objects.create_user(
            username="xp_api_ops",
            password="pass1234",
            first_name="Ops",
            email="xp_api_ops@example.com",
        )

        ops_role, _ = Role.objects.update_or_create(
            slug=RoleSlug.OPS_MANAGER,
            defaults={"name": "Ops Manager"},
        )
        self.ops.roles.add(ops_role)

        XPLedger.objects.create(
            user=self.tech_one,
            amount=3,
            entry_type=XPLedgerEntryType.TICKET_BASE_XP,
            reference="ticket_base_xp:101",
            payload={"ticket_id": 101},
        )
        XPLedger.objects.create(
            user=self.tech_one,
            amount=1,
            entry_type=XPLedgerEntryType.TICKET_QC_FIRST_PASS_BONUS,
            reference="ticket_qc_first_pass_bonus:101",
            payload={"ticket_id": 101},
        )
        XPLedger.objects.create(
            user=self.tech_one,
            amount=2,
            entry_type=XPLedgerEntryType.ATTENDANCE_PUNCTUALITY,
            reference="attendance_checkin:tech_one:2026-02-11",
            payload={},
        )
        XPLedger.objects.create(
            user=self.tech_two,
            amount=4,
            entry_type=XPLedgerEntryType.TICKET_BASE_XP,
            reference="ticket_base_xp:202",
            payload={"ticket_id": 202},
        )

    def test_regular_user_sees_only_own_entries(self):
        self.client.force_authenticate(user=self.tech_one)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

        entries = resp.data["data"]
        self.assertEqual(len(entries), 3)
        self.assertTrue(all(item["user"] == self.tech_one.id for item in entries))

    def test_regular_user_cannot_read_other_user_entries(self):
        self.client.force_authenticate(user=self.tech_one)
        resp = self.client.get(f"{self.url}?user_id={self.tech_two.id}")
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(resp.data["success"])

    def test_ops_can_filter_by_user_and_ticket(self):
        self.client.force_authenticate(user=self.ops)

        by_user = self.client.get(f"{self.url}?user_id={self.tech_two.id}")
        self.assertEqual(by_user.status_code, 200)
        self.assertEqual(len(by_user.data["data"]), 1)
        self.assertEqual(by_user.data["data"][0]["user"], self.tech_two.id)

        by_ticket = self.client.get(f"{self.url}?user_id={self.tech_one.id}&ticket_id=101")
        self.assertEqual(by_ticket.status_code, 200)
        self.assertEqual(len(by_ticket.data["data"]), 2)
        refs = {item["reference"] for item in by_ticket.data["data"]}
        self.assertIn("ticket_base_xp:101", refs)
        self.assertIn("ticket_qc_first_pass_bonus:101", refs)

    def test_invalid_filters_return_400(self):
        self.client.force_authenticate(user=self.ops)

        invalid_limit = self.client.get(f"{self.url}?limit=abc")
        self.assertEqual(invalid_limit.status_code, 400)

        invalid_ticket = self.client.get(f"{self.url}?ticket_id=-1")
        self.assertEqual(invalid_ticket.status_code, 400)

        invalid_entry_type = self.client.get(f"{self.url}?entry_type=unknown_entry")
        self.assertEqual(invalid_entry_type.status_code, 400)
