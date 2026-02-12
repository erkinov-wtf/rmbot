import pytest

from bike.models import Bike
from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db


LIST_URL = "/api/v1/bikes/"
CREATE_URL = "/api/v1/bikes/create/"
SUGGEST_URL = "/api/v1/bikes/suggest/"


def test_list_requires_auth(api_client):
    resp = api_client.get(LIST_URL)
    assert resp.status_code == 401


def test_create_requires_bike_manager_role(authed_client_factory, user_factory):
    regular_user = user_factory(
        username="regular_bike",
        first_name="Regular",
        email="regular_bike@example.com",
    )
    client = authed_client_factory(regular_user)

    resp = client.post(CREATE_URL, {"bike_code": "RM-0200"}, format="json")
    assert resp.status_code == 403


def test_ops_manager_can_create_bike(authed_client_factory, user_factory, assign_roles):
    manager_user = user_factory(
        username="ops_bike",
        first_name="Ops",
        email="ops_bike@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)

    resp = client.post(CREATE_URL, {"bike_code": "RM-0200"}, format="json")

    assert resp.status_code == 201
    assert resp.data["data"]["bike_code"] == "RM-0200"
    assert Bike.objects.count() == 1


def test_create_rejects_invalid_bike_code_format(
    authed_client_factory, user_factory, assign_roles
):
    manager_user = user_factory(
        username="ops_bike_regex",
        first_name="Ops",
        email="ops_bike_regex@example.com",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    client = authed_client_factory(manager_user)

    resp = client.post(CREATE_URL, {"bike_code": "bike-0200"}, format="json")

    assert resp.status_code == 400
    assert "pattern" in resp.data["message"].lower()


def test_suggest_requires_auth(api_client):
    resp = api_client.get(SUGGEST_URL, {"q": "RM"})
    assert resp.status_code == 401


def test_suggest_returns_matches_for_query(
    authed_client_factory, user_factory, bike_factory
):
    user = user_factory(
        username="bike_reader",
        first_name="Reader",
        email="bike_reader@example.com",
    )
    bike_factory(bike_code="RM-0100")
    bike_factory(bike_code="RM-0101")
    bike_factory(bike_code="RM-0200")
    client = authed_client_factory(user)

    resp = client.get(SUGGEST_URL, {"q": "rm-01"})

    assert resp.status_code == 200
    suggestions = resp.data["data"]["suggestions"]
    assert "RM-0100" in suggestions
    assert "RM-0101" in suggestions


def test_suggest_rejects_short_query(authed_client_factory, user_factory):
    user = user_factory(
        username="bike_reader_short",
        first_name="Reader",
        email="bike_reader_short@example.com",
    )
    client = authed_client_factory(user)

    resp = client.get(SUGGEST_URL, {"q": "R"})

    assert resp.status_code == 400
    assert "at least 2" in resp.data["message"].lower()
