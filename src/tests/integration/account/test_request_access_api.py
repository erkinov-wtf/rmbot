import pytest

from account.models import AccessRequest
from core.utils.constants import AccessRequestStatus

pytestmark = pytest.mark.django_db


REQUEST_ACCESS_URL = "/api/v1/users/request-access/"
ME_URL = "/api/v1/users/me/"


def test_creates_pending_access_request(api_client):
    payload = {
        "telegram_id": 12345,
        "username": "alice",
        "first_name": "Alice",
        "phone": "+998901234567",
        "note": "Need access for technician onboarding",
    }

    resp = api_client.post(REQUEST_ACCESS_URL, payload, format="json")

    assert resp.status_code == 201
    assert AccessRequest.objects.count() == 1
    obj = AccessRequest.objects.first()
    assert obj.status == AccessRequestStatus.PENDING
    assert obj.phone == payload["phone"]
    assert obj.note == payload["note"]
    assert resp.data["data"]["status"] == AccessRequestStatus.PENDING


def test_prevents_duplicate_pending(api_client):
    AccessRequest.objects.create(
        telegram_id=12345,
        username="alice",
        status=AccessRequestStatus.PENDING,
    )

    resp = api_client.post(REQUEST_ACCESS_URL, {"telegram_id": 12345}, format="json")

    assert resp.status_code == 400
    assert resp.data["success"] is False
    assert "telegram" in resp.data["message"].lower()
    assert AccessRequest.objects.count() == 1


def test_me_requires_auth(api_client):
    resp = api_client.get(ME_URL)
    assert resp.status_code == 401


def test_me_returns_user_when_authenticated(authed_client_factory, user_factory):
    user = user_factory(
        username="bob",
        first_name="Bob",
        email="bob@example.com",
    )
    client = authed_client_factory(user)

    resp = client.get(ME_URL)

    assert resp.status_code == 200
    assert resp.data["data"]["username"] == "bob"
