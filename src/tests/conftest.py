import itertools
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from account.models import Role, User
from core.utils.constants import RoleSlug, TicketStatus
from inventory.models import InventoryItem
from inventory.services import InventoryItemService
from ticket.models import Ticket

ROLE_NAMES = {
    RoleSlug.SUPER_ADMIN: "Super Admin",
    RoleSlug.OPS_MANAGER: "Ops Manager",
    RoleSlug.MASTER: "Master (Service Lead)",
    RoleSlug.TECHNICIAN: "Technician",
    RoleSlug.QC_INSPECTOR: "QC Inspector",
}


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authed_client_factory() -> Callable[[User], APIClient]:
    def _make(user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _make


@pytest.fixture
def user_factory(db) -> Callable[..., User]:
    seq = itertools.count(1)

    def _create_user(**overrides) -> User:
        idx = next(seq)
        payload = {
            "username": f"user_{idx}",
            "password": "pass1234",
            "first_name": "User",
            "email": f"user_{idx}@example.com",
        }
        payload.update(overrides)
        return User.objects.create_user(**payload)

    return _create_user


@pytest.fixture
def role_factory(db) -> Callable[..., Role]:
    def _create_role(slug: str, *, name: str | None = None) -> Role:
        role, _ = Role.objects.update_or_create(
            slug=slug,
            defaults={"name": name or ROLE_NAMES.get(slug, str(slug))},
        )
        return role

    return _create_role


@pytest.fixture
def assign_roles(role_factory) -> Callable[..., User]:
    def _assign(user: User, *slugs: str) -> User:
        for slug in slugs:
            user.roles.add(role_factory(slug))
        return user

    return _assign


@pytest.fixture
def inventory_item_factory(db) -> Callable[..., InventoryItem]:
    seq = itertools.count(1000)

    def _create_inventory_item(**overrides) -> InventoryItem:
        serial_number = overrides.pop(
            "serial_number",
            overrides.pop("serial_number", f"RM-{next(seq):04d}"),
        )
        inventory = overrides.pop(
            "inventory",
            InventoryItemService.get_default_inventory(),
        )
        category = overrides.pop(
            "category",
            InventoryItemService.get_default_category(),
        )
        name = overrides.pop("name", serial_number)
        return InventoryItem.objects.create(
            serial_number=serial_number,
            name=name,
            inventory=inventory,
            category=category,
            **overrides,
        )

    return _create_inventory_item


@pytest.fixture
def ticket_factory(db, inventory_item_factory, user_factory) -> Callable[..., Ticket]:
    def _create_ticket(**overrides) -> Ticket:
        inventory_item = overrides.pop(
            "inventory_item",
            overrides.pop("inventory", inventory_item_factory()),
        )
        master = overrides.pop("master", user_factory(first_name="Master"))
        payload = {
            "inventory_item": inventory_item,
            "master": master,
            "status": overrides.pop("status", TicketStatus.UNDER_REVIEW),
            "title": overrides.pop("title", "Ticket"),
        }
        payload.update(overrides)
        return Ticket.objects.create(**payload)

    return _create_ticket
