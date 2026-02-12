import pytest

pytestmark = pytest.mark.django_db


REQUEST_ACCESS_URL = "/api/v1/users/request-access/"
ME_URL = "/api/v1/users/me/"


def test_request_access_endpoint_is_not_available(api_client):
    resp = api_client.post(
        REQUEST_ACCESS_URL,
        {"telegram_id": 12345},
        format="json",
    )
    assert resp.status_code == 404


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
