from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from account.models import Role, User
from api.v1.ticket.views import TicketViewSet
from core.utils.constants import RoleSlug, TicketColor, TicketStatus
from inventory.models import Inventory, InventoryItem, InventoryItemCategory, InventoryItemPart
from ticket.models import Ticket, TicketPartSpec


def _role(*, slug: str) -> Role:
    role, _ = Role.objects.get_or_create(
        slug=slug,
        defaults={"name": slug.replace("_", " ").title()},
    )
    return role


def _user(*, username: str, role_slug: str) -> User:
    user = User.objects.create_user(
        username=username,
        password="pass1234",
        first_name=username,
        is_active=True,
    )
    user.roles.add(_role(slug=role_slug))
    return user


@pytest.mark.django_db
def test_ticket_update_view_allows_other_technician_for_open_ticket():
    suffix = uuid.uuid4().hex[:6]
    inventory = Inventory.objects.create(name=f"inv-view-{suffix}")
    category = InventoryItemCategory.objects.create(name=f"cat-view-{suffix}")
    item = InventoryItem.objects.create(
        inventory=inventory,
        category=category,
        name=f"item-view-{suffix}",
        serial_number=f"VIEW-{suffix}",
    )
    part = InventoryItemPart.objects.create(category=category, name=f"part-view-{suffix}")
    owner = _user(username=f"owner_{suffix}", role_slug=RoleSlug.TECHNICIAN)
    outsider = _user(username=f"outsider_{suffix}", role_slug=RoleSlug.TECHNICIAN)
    ticket = Ticket.objects.create(
        inventory_item=item,
        master=owner,
        status=TicketStatus.NEW,
        title="Owner ticket",
        total_duration=20,
        flag_minutes=20,
        xp_amount=1,
    )
    TicketPartSpec.objects.create(
        ticket=ticket,
        inventory_item_part=part,
        color=TicketColor.GREEN,
        minutes=10,
    )

    request = APIRequestFactory().patch(
        f"/api/v1/tickets/{ticket.id}/",
        {"title": "Intruder edit"},
        format="json",
    )
    force_authenticate(request, user=outsider)

    response = TicketViewSet.as_view({"patch": "partial_update"})(request, pk=ticket.id)

    assert response.status_code == 200
    assert response.data["title"] == "Intruder edit"

    ticket.refresh_from_db()
    assert ticket.title == "Intruder edit"
