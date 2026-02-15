import pytest
from django.test import Client

from core.utils.constants import RoleSlug, TicketStatus
from ticket.models import TicketTransition

pytestmark = pytest.mark.django_db


@pytest.fixture
def webhook_settings(settings):
    settings.BOT_MODE = "webhook"
    settings.BOT_WEBHOOK_SECRET = "expected-secret"
    return settings


def test_webhook_rejects_invalid_secret_under_burst(webhook_settings):
    client = Client()

    for _ in range(25):
        resp = client.post(
            "/bot/webhook/",
            data="{}",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong-secret",
        )
        assert resp.status_code == 403


def test_webhook_rejects_invalid_json_under_burst(webhook_settings):
    client = Client()

    for _ in range(15):
        resp = client.post(
            "/bot/webhook/",
            data="{invalid",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="expected-secret",
        )
        assert resp.status_code == 400


def test_rbac_bypass_burst_cannot_assign_ticket(
    authed_client_factory,
    user_factory,
    assign_roles,
    inventory_item_factory,
    ticket_factory,
):
    master = user_factory(
        username="rbac_master",
        first_name="RBAC Master",
        email="rbac_master@example.com",
    )
    technician = user_factory(
        username="rbac_technician",
        first_name="RBAC Technician",
        email="rbac_technician@example.com",
    )
    attacker = user_factory(
        username="rbac_attacker",
        first_name="RBAC Attacker",
        email="rbac_attacker@example.com",
    )

    assign_roles(master, RoleSlug.MASTER)
    assign_roles(technician, RoleSlug.TECHNICIAN)

    ticket = ticket_factory(
        inventory_item=inventory_item_factory(serial_number="RM-RBAC-0001"),
        master=master,
        status=TicketStatus.UNDER_REVIEW,
        title="RBAC test",
    )

    attacker_client = authed_client_factory(attacker)

    for _ in range(20):
        resp = attacker_client.post(
            f"/api/v1/tickets/{ticket.id}/assign/",
            {
                "technician_id": technician.id,
                "role_slugs": [RoleSlug.MASTER],
                "is_superuser": True,
            },
            format="json",
        )
        assert resp.status_code == 403

    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.UNDER_REVIEW
    assert ticket.technician_id is None
    assert TicketTransition.objects.filter(ticket=ticket).count() == 0
