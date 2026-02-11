import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from account.models import TelegramProfile

pytestmark = pytest.mark.django_db


VERIFY_URL = "/api/v1/auth/tma/verify/"


def build_init_data(bot_token: str, user_payload: dict) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(data)


@pytest.fixture
def tma_settings(settings):
    settings.BOT_TOKEN = "TEST_BOT_TOKEN"
    return settings


@pytest.fixture
def tg_user_payload():
    return {
        "id": 1111,
        "username": "tguser",
        "first_name": "TG",
        "last_name": "User",
        "language_code": "en",
        "is_premium": False,
        "is_bot": False,
    }


def test_returns_tokens_when_user_linked(
    api_client, user_factory, tma_settings, tg_user_payload
):
    user = user_factory(
        username="alice",
        password="password",
        first_name="Alice",
        email="alice@example.com",
    )
    TelegramProfile.objects.create(
        user=user,
        telegram_id=tg_user_payload["id"],
        username=tg_user_payload["username"],
    )

    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["user_exists"] is True
    assert "access" in payload
    assert "refresh" in payload
    assert payload["user"]["id"] == user.id


def test_requires_access_when_no_linked_user(api_client, tma_settings, tg_user_payload):
    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["valid"] is True
    assert payload["user_exists"] is False
    assert payload["needs_access_request"] is True


def test_rejects_invalid_hash(api_client, tma_settings, tg_user_payload):
    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload) + "tampered"
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "hash" in resp.data["error"]["detail"].lower()


def test_rejects_missing_user_id(api_client, tma_settings):
    bad_payload = {
        "username": "tguser",
        "first_name": "TG",
    }
    init_data = build_init_data("TEST_BOT_TOKEN", bad_payload)
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "user.id" in resp.data["error"]["detail"]
