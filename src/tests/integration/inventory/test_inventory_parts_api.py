import pytest

from core.utils.constants import RoleSlug
from inventory.models import InventoryItemCategory, InventoryItemPart

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
        {"name": "RM-ENGINE", "category": inventory_item.category_id},
        format="json",
    )

    assert resp.status_code == 403


def test_ops_manager_can_create_category_part(
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
        {"name": "RM-HANDLE", "category": inventory_item.category_id},
        format="json",
    )

    assert resp.status_code == 201
    assert resp.data["data"]["category"] == inventory_item.category_id
    assert InventoryItemPart.objects.filter(
        name="RM-HANDLE",
        category_id=inventory_item.category_id,
    ).exists()


def test_part_name_uniqueness_is_scoped_to_category(
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
    category_a = InventoryItemCategory.objects.create(name="Category A")
    category_b = InventoryItemCategory.objects.create(name="Category B")
    inventory_item_a = inventory_item_factory(
        serial_number="RM-PART-0100", category=category_a
    )
    inventory_item_b = inventory_item_factory(
        serial_number="RM-PART-0101", category=category_b
    )
    client = authed_client_factory(manager_user)

    InventoryItemPart.objects.create(
        name="RM-SEAT",
        category=inventory_item_a.category,
        inventory_item=inventory_item_a,
    )

    same_item_resp = client.post(
        PART_LIST_URL,
        {"name": "RM-SEAT", "category": inventory_item_a.category_id},
        format="json",
    )
    assert same_item_resp.status_code == 400

    other_category_resp = client.post(
        PART_LIST_URL,
        {"name": "RM-SEAT", "category": inventory_item_b.category_id},
        format="json",
    )
    assert other_category_resp.status_code == 201
    assert InventoryItemPart.objects.filter(name="RM-SEAT").count() == 2
