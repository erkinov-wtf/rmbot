import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from rest_framework.test import APIClient

from account.models import TelegramProfile
from core.utils.constants import (
    InventoryItemStatus,
    RoleSlug,
    TicketStatus,
    WorkSessionStatus,
)
from inventory.models import InventoryItemPart
from ticket.models import WorkSession

pytestmark = pytest.mark.django_db

VERIFY_URL = "/api/v1/auth/tma/verify/"


@pytest.fixture
def tma_settings(settings):
    settings.BOT_TOKEN = "TEST_BOT_TOKEN"
    settings.TMA_INIT_DATA_MAX_AGE_SECONDS = 300
    settings.TMA_INIT_DATA_MAX_FUTURE_SKEW_SECONDS = 30
    settings.TMA_INIT_DATA_REPLAY_TTL_SECONDS = 300
    return settings


def build_init_data(bot_token: str, user_payload: dict) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(int(time.time())),
        "query_id": str(time.time_ns()),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(data)


def _client_from_tma_verify(
    *, api_client: APIClient, bot_token: str, user_payload: dict
) -> APIClient:
    init_data = build_init_data(bot_token, user_payload)
    verify = api_client.post(VERIFY_URL, {"init_data": init_data}, format="json")
    assert verify.status_code == 200
    assert verify.data["data"]["user_exists"] is True

    access = verify.data["data"]["access"]
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


def test_tma_e2e_master_to_technician_to_qc(
    api_client,
    tma_settings,
    user_factory,
    assign_roles,
    inventory_item_factory,
):
    master = user_factory(
        username="tma_master",
        first_name="Master",
        email="tma_master@example.com",
    )
    technician = user_factory(
        username="tma_technician",
        first_name="Technician",
        email="tma_technician@example.com",
    )
    ops = user_factory(
        username="tma_ops",
        first_name="Ops",
        email="tma_ops@example.com",
    )
    qc = user_factory(
        username="tma_qc",
        first_name="QC",
        email="tma_qc@example.com",
    )

    assign_roles(master, RoleSlug.MASTER)
    assign_roles(technician, RoleSlug.TECHNICIAN)
    assign_roles(ops, RoleSlug.OPS_MANAGER)
    assign_roles(qc, RoleSlug.QC_INSPECTOR)

    TelegramProfile.objects.create(user=master, telegram_id=50001, username="master_tg")
    TelegramProfile.objects.create(
        user=technician,
        telegram_id=50002,
        username="technician_tg",
    )
    TelegramProfile.objects.create(user=ops, telegram_id=50004, username="ops_tg")
    TelegramProfile.objects.create(user=qc, telegram_id=50003, username="qc_tg")

    master_client = _client_from_tma_verify(
        api_client=api_client,
        bot_token=tma_settings.BOT_TOKEN,
        user_payload={
            "id": 50001,
            "username": "master_tg",
            "first_name": "Master",
            "last_name": "Flow",
            "is_bot": False,
        },
    )
    technician_client = _client_from_tma_verify(
        api_client=api_client,
        bot_token=tma_settings.BOT_TOKEN,
        user_payload={
            "id": 50002,
            "username": "technician_tg",
            "first_name": "Technician",
            "last_name": "Flow",
            "is_bot": False,
        },
    )
    ops_client = _client_from_tma_verify(
        api_client=api_client,
        bot_token=tma_settings.BOT_TOKEN,
        user_payload={
            "id": 50004,
            "username": "ops_tg",
            "first_name": "Ops",
            "last_name": "Flow",
            "is_bot": False,
        },
    )
    qc_client = _client_from_tma_verify(
        api_client=api_client,
        bot_token=tma_settings.BOT_TOKEN,
        user_payload={
            "id": 50003,
            "username": "qc_tg",
            "first_name": "QC",
            "last_name": "Flow",
            "is_bot": False,
        },
    )

    inventory_item = inventory_item_factory(
        serial_number="RM-TMA-0001", status=InventoryItemStatus.READY, is_active=True
    )
    part_a = InventoryItemPart.objects.create(name="RM-TMA-PART-A")
    part_b = InventoryItemPart.objects.create(name="RM-TMA-PART-B")
    inventory_item.parts.set([part_a, part_b])

    create = master_client.post(
        "/api/v1/tickets/create/",
        {
            "serial_number": inventory_item.serial_number,
            "title": "TMA E2E flow ticket",
            "checklist_snapshot": [f"Task {idx}" for idx in range(1, 11)],
            "part_specs": [
                {
                    "part_id": part_a.id,
                    "color": "green",
                    "comment": "Inspect",
                    "minutes": 20,
                },
                {
                    "part_id": part_b.id,
                    "color": "yellow",
                    "comment": "Repair",
                    "minutes": 25,
                },
            ],
        },
        format="json",
    )
    assert create.status_code == 201
    ticket_id = create.data["data"]["id"]
    assert create.data["data"]["status"] == TicketStatus.UNDER_REVIEW

    assign = ops_client.post(
        f"/api/v1/tickets/{ticket_id}/assign/",
        {"technician_id": technician.id},
        format="json",
    )
    assert assign.status_code == 200

    start = technician_client.post(
        f"/api/v1/tickets/{ticket_id}/start/", {}, format="json"
    )
    assert start.status_code == 200
    assert start.data["data"]["status"] == TicketStatus.IN_PROGRESS
    assert WorkSession.objects.filter(
        ticket_id=ticket_id,
        technician=technician,
        status=WorkSessionStatus.RUNNING,
    ).exists()

    stop = technician_client.post(
        f"/api/v1/tickets/{ticket_id}/work-session/stop/",
        {},
        format="json",
    )
    assert stop.status_code == 200
    assert stop.data["data"]["status"] == WorkSessionStatus.STOPPED

    to_qc = technician_client.post(
        f"/api/v1/tickets/{ticket_id}/to-waiting-qc/", {}, format="json"
    )
    assert to_qc.status_code == 200
    assert to_qc.data["data"]["status"] == TicketStatus.WAITING_QC

    qc_pass = qc_client.post(f"/api/v1/tickets/{ticket_id}/qc-pass/", {}, format="json")
    assert qc_pass.status_code == 200
    assert qc_pass.data["data"]["status"] == TicketStatus.DONE
