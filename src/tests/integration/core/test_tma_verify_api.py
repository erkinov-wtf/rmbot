import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from account.models import TelegramProfile
from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db


VERIFY_URL = "/api/v1/auth/tma/verify/"


def build_init_data(
    bot_token: str,
    user_payload: dict,
    *,
    auth_date: int | None = None,
) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
        "query_id": str(time.time_ns()),
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
    settings.TMA_INIT_DATA_MAX_AGE_SECONDS = 300
    settings.TMA_INIT_DATA_MAX_FUTURE_SKEW_SECONDS = 30
    settings.TMA_INIT_DATA_REPLAY_TTL_SECONDS = 300
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
    api_client, user_factory, assign_roles, tma_settings, tg_user_payload
):
    user = user_factory(
        username="alice",
        password="password",
        first_name="Alice",
    )
    TelegramProfile.objects.create(
        user=user,
        telegram_id=tg_user_payload["id"],
        username=tg_user_payload["username"],
    )
    assign_roles(user, RoleSlug.MASTER)

    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["user_exists"] is True
    assert "access" in payload
    assert "refresh" in payload
    assert sorted(payload["role_slugs"]) == [RoleSlug.MASTER]
    assert payload["permissions"]["can_create"] is True
    assert payload["permissions"]["can_review"] is True
    assert payload["permissions"]["can_assign"] is True
    assert payload["permissions"]["can_manual_metrics"] is True
    assert payload["permissions"]["can_open_review_panel"] is True
    assert payload["permissions"]["can_approve_and_assign"] is True
    assert payload["user"]["id"] == user.id
    claims = AccessToken(payload["access"])
    assert claims["role_slugs"] == [RoleSlug.MASTER]
    assert claims["roles"] == ["Master (Service Lead)"]


def test_requires_access_when_no_linked_user(api_client, tma_settings, tg_user_payload):
    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["valid"] is True
    assert payload["user_exists"] is False
    assert payload["needs_access_request"] is True
    assert payload["role_slugs"] == []
    assert payload["roles"] == []
    assert payload["permissions"]["can_create"] is False
    assert payload["permissions"]["can_review"] is False
    assert payload["permissions"]["can_assign"] is False


def test_links_active_user_by_phone_when_profile_link_missing(
    api_client, user_factory, tg_user_payload, tma_settings
):
    user = user_factory(
        username="phone_linked_user",
        first_name="Phone",
        phone="+998901112233",
    )
    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)

    resp = api_client.post(
        VERIFY_URL,
        {"init_data": init_data, "phone": "998901112233"},
        format="json",
    )

    assert resp.status_code == 200
    payload = resp.data["data"]
    assert payload["valid"] is True
    assert payload["user_exists"] is True
    assert payload["user"]["id"] == user.id


def test_linked_user_without_roles_has_zero_permissions(
    api_client, user_factory, tma_settings, tg_user_payload
):
    user = user_factory(
        username="no_roles_user",
        first_name="NoRoles",
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
    assert payload["role_slugs"] == []
    assert payload["roles"] == []
    assert payload["permissions"]["can_create"] is False
    assert payload["permissions"]["can_review"] is False
    assert payload["permissions"]["can_assign"] is False
    assert payload["permissions"]["can_open_review_panel"] is False


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


def test_rejects_replayed_init_data_for_linked_user(
    api_client, user_factory, tma_settings, tg_user_payload
):
    user = user_factory(
        username="bob",
        password="password",
        first_name="Bob",
    )
    TelegramProfile.objects.create(
        user=user,
        telegram_id=tg_user_payload["id"],
        username=tg_user_payload["username"],
    )

    init_data = build_init_data("TEST_BOT_TOKEN", tg_user_payload)

    first_resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")
    second_resp = api_client.post(
        VERIFY_URL,
        {"init_data": init_data},
        format="json",
    )

    assert first_resp.status_code == 200
    assert second_resp.status_code == 400
    assert second_resp.data["success"] is False
    assert "already been used" in second_resp.data["error"]["detail"]


def test_rejects_auth_date_far_in_future(api_client, tma_settings, tg_user_payload):
    init_data = build_init_data(
        "TEST_BOT_TOKEN",
        tg_user_payload,
        auth_date=int(time.time()) + 120,
    )
    resp = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "future" in resp.data["error"]["detail"].lower()
