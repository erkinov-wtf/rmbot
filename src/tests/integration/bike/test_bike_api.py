import pytest

from bike.models import Bike
from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db


LIST_URL = "/api/v1/bikes/"
CREATE_URL = "/api/v1/bikes/create/"


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
