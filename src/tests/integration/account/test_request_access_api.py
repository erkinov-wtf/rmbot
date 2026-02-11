from django.test import TestCase
from rest_framework.test import APIClient

from account.models import AccessRequest
from core.utils.constants import AccessRequestStatus


class RequestAccessAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/users/request-access/"

    def test_creates_pending_access_request(self):
        payload = {
            "telegram_id": 12345,
            "username": "alice",
            "first_name": "Alice",
            "phone": "+998901234567",
            "note": "Need access for technician onboarding",
        }
        resp = self.client.post(self.url, payload, format="json")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AccessRequest.objects.count(), 1)
        obj = AccessRequest.objects.first()
        self.assertEqual(obj.status, AccessRequestStatus.PENDING)
        self.assertEqual(obj.phone, payload["phone"])
        self.assertEqual(obj.note, payload["note"])
        self.assertEqual(resp.data["data"]["status"], AccessRequestStatus.PENDING)

    def test_prevents_duplicate_pending(self):
        AccessRequest.objects.create(
            telegram_id=12345,
            username="alice",
            status=AccessRequestStatus.PENDING,
        )

        resp = self.client.post(self.url, {"telegram_id": 12345}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data["success"], False)
        self.assertIn("telegram", resp.data["message"].lower())
        self.assertEqual(AccessRequest.objects.count(), 1)


class MeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/users/me/"

    def test_requires_auth(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 401)

    def test_returns_user_when_authenticated(self):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="bob",
            password="pass1234",
            first_name="Bob",
            email="bob@example.com",
        )
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["username"], "bob")
