from django.test import TestCase
from rest_framework.test import APIClient

from account.models import User
from attendance.models import AttendanceRecord
from core.utils.constants import XPLedgerEntryType
from gamification.models import XPLedger


class AttendanceAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="attendance_user",
            password="pass1234",
            first_name="Attendance",
            email="attendance@example.com",
        )
        self.client.force_authenticate(user=self.user)

    def test_checkin_creates_record_and_xp_entry(self):
        resp = self.client.post("/api/v1/attendance/checkin/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(XPLedger.objects.count(), 1)

        entry = XPLedger.objects.first()
        self.assertEqual(entry.entry_type, XPLedgerEntryType.ATTENDANCE_PUNCTUALITY)
        self.assertIn("attendance_checkin", entry.reference)
        self.assertIn("xp_awarded", resp.data["data"])

    def test_checkin_twice_fails(self):
        self.client.post("/api/v1/attendance/checkin/", {}, format="json")
        second = self.client.post("/api/v1/attendance/checkin/", {}, format="json")
        self.assertEqual(second.status_code, 400)
        self.assertFalse(second.data["success"])
        self.assertIn("already checked in", second.data["error"]["detail"].lower())

    def test_checkout_requires_checkin(self):
        resp = self.client.post("/api/v1/attendance/checkout/", {}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("before check in", resp.data["error"]["detail"].lower())

    def test_checkout_after_checkin_succeeds(self):
        self.client.post("/api/v1/attendance/checkin/", {}, format="json")
        resp = self.client.post("/api/v1/attendance/checkout/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

        record = AttendanceRecord.objects.get(user=self.user)
        self.assertIsNotNone(record.check_out_at)

    def test_today_endpoint_returns_current_record(self):
        before = self.client.get("/api/v1/attendance/today/")
        self.assertEqual(before.status_code, 200)
        self.assertIsNone(before.data["data"])

        self.client.post("/api/v1/attendance/checkin/", {}, format="json")
        after = self.client.get("/api/v1/attendance/today/")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data["data"]["user"], self.user.id)
