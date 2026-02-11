import itertools
from collections.abc import Callable

import pytest
from rest_framework.test import APIClient

from account.models import Role, User
from bike.models import Bike
from core.utils.constants import RoleSlug, TicketStatus
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
def bike_factory(db) -> Callable[..., Bike]:
    seq = itertools.count(1000)

    def _create_bike(**overrides) -> Bike:
        code = overrides.pop("bike_code", f"RM-{next(seq):04d}")
        return Bike.objects.create(bike_code=code, **overrides)

    return _create_bike


@pytest.fixture
def ticket_factory(db, bike_factory, user_factory) -> Callable[..., Ticket]:
    def _create_ticket(**overrides) -> Ticket:
        bike = overrides.pop("bike", bike_factory())
        master = overrides.pop("master", user_factory(first_name="Master"))
        payload = {
            "bike": bike,
            "master": master,
            "status": overrides.pop("status", TicketStatus.NEW),
            "title": overrides.pop("title", "Ticket"),
        }
        payload.update(overrides)
        return Ticket.objects.create(**payload)

    return _create_ticket
