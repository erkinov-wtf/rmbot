import hmac
import hashlib
import json
import time
from urllib.parse import urlencode

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from account.models import TelegramProfile, User


def build_init_data(bot_token: str, user_payload: dict) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


@override_settings(BOT_TOKEN="TEST_BOT_TOKEN", LOGS_ROOT="/home/mehroj/PycharmProjects/RentMarket/logs")
class TMAInitDataVerifyAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/v1/auth/tma/verify/"
        self.user_payload = {
            "id": 1111,
            "username": "tguser",
            "first_name": "TG",
            "last_name": "User",
            "language_code": "en",
            "is_premium": False,
            "is_bot": False,
        }

    def test_returns_tokens_when_user_linked(self):
        user = User.objects.create_user(
            username="alice",
            password="password",
            first_name="Alice",
            email="alice@example.com",
        )
        TelegramProfile.objects.create(
            user=user,
            telegram_id=self.user_payload["id"],
            username=self.user_payload["username"],
        )

        init_data = build_init_data("TEST_BOT_TOKEN", self.user_payload)
        resp = self.client.post(self.url, {"init_data": init_data}, format="json")

        self.assertEqual(resp.status_code, 200)
        payload = resp.data["data"]
        self.assertTrue(payload["user_exists"])
        self.assertIn("access", payload)
        self.assertIn("refresh", payload)
        self.assertEqual(payload["user"]["id"], user.id)

    def test_requires_access_when_no_linked_user(self):
        init_data = build_init_data("TEST_BOT_TOKEN", self.user_payload)
        resp = self.client.post(self.url, {"init_data": init_data}, format="json")

        self.assertEqual(resp.status_code, 200)
        payload = resp.data["data"]
        self.assertTrue(payload["valid"])
        self.assertFalse(payload["user_exists"])
        self.assertTrue(payload["needs_access_request"])

    def test_rejects_invalid_hash(self):
        init_data = build_init_data("TEST_BOT_TOKEN", self.user_payload) + "tampered"
        resp = self.client.post(self.url, {"init_data": init_data}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("hash", resp.data["error"]["detail"].lower())

    def test_rejects_missing_user_id(self):
        bad_payload = {
            "username": "tguser",
            "first_name": "TG",
        }
        init_data = build_init_data("TEST_BOT_TOKEN", bad_payload)
        resp = self.client.post(self.url, {"init_data": init_data}, format="json")

        self.assertEqual(resp.status_code, 400)
        self.assertFalse(resp.data["success"])
        self.assertIn("user.id", resp.data["error"]["detail"])
