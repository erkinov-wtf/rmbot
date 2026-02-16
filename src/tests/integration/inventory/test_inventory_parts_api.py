import pytest

from core.utils.constants import RoleSlug
from inventory.models import InventoryItemPart

pytestmark = pytest.mark.django_db

PART_LIST_URL = "/api/v1/inventory/parts/"


def test_create_part_requires_inventory_manager_role(
    authed_client_factory,
    user_factory,
    inventory_item_factory,
):
    regular_user = user_factory(
        username="inventory_part_regular",
        first_name="Regular",
    )
    inventory_item = inventory_item_factory(serial_number="RM-PART-0001")
    client = authed_client_factory(regular_user)

    resp = client.post(
        PART_LIST_URL,
        {"name": "RM-ENGINE", "inventory_item": inventory_item.id},
        format="json",
    )

    assert resp.status_code == 403


def test_ops_manager_can_create_inventory_item_part(
    authed_client_factory,
    user_factory,
    assign_roles,
    inventory_item_factory,
):
    manager_user = user_factory(
        username="inventory_part_ops",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    inventory_item = inventory_item_factory(serial_number="RM-PART-0002")
    client = authed_client_factory(manager_user)

    resp = client.post(
        PART_LIST_URL,
        {"name": "RM-HANDLE", "inventory_item": inventory_item.id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["data"]["inventory_item"] == inventory_item.id
    assert InventoryItemPart.objects.filter(
        name="RM-HANDLE",
        inventory_item=inventory_item,
    ).exists()


def test_part_name_uniqueness_is_scoped_to_inventory_item(
    authed_client_factory,
    user_factory,
    assign_roles,
    inventory_item_factory,
):
    manager_user = user_factory(
        username="inventory_part_scope_ops",
        first_name="Ops",
    )
    assign_roles(manager_user, RoleSlug.OPS_MANAGER)
    inventory_item_a = inventory_item_factory(serial_number="RM-PART-0100")
    inventory_item_b = inventory_item_factory(serial_number="RM-PART-0101")
    client = authed_client_factory(manager_user)

    InventoryItemPart.objects.create(
        name="RM-SEAT",
        inventory_item=inventory_item_a,
    )

    same_item_resp = client.post(
        PART_LIST_URL,
        {"name": "RM-SEAT", "inventory_item": inventory_item_a.id},
        format="json",
    )
    assert same_item_resp.status_code == 400

    other_item_resp = client.post(
        PART_LIST_URL,
        {"name": "RM-SEAT", "inventory_item": inventory_item_b.id},
        format="json",
    )
    assert other_item_resp.status_code == 201
    assert InventoryItemPart.objects.filter(name="RM-SEAT").count() == 2
