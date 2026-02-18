from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from core.utils.constants import EmployeeLevel, RoleSlug, XPTransactionEntryType
from gamification.models import UserLevelHistoryEvent, XPTransaction

pytestmark = pytest.mark.django_db


LEVEL_OVERVIEW_URL = "/api/v1/xp/levels/overview/"
LEVEL_SET_URL_TEMPLATE = "/api/v1/xp/levels/users/{user_id}/set-level/"
LEVEL_HISTORY_URL_TEMPLATE = "/api/v1/xp/levels/users/{user_id}/history/"


def _create_xp_entry(
    *,
    user_id: int,
    amount: int,
    reference: str,
    created_at: datetime,
) -> XPTransaction:
    entry = XPTransaction.objects.create(
        user_id=user_id,
        amount=amount,
        entry_type=XPTransactionEntryType.MANUAL_ADJUSTMENT,
        reference=reference,
        payload={},
    )
    XPTransaction.all_objects.filter(pk=entry.pk).update(
        created_at=created_at,
        updated_at=created_at,
    )
    return entry


@pytest.fixture
def level_control_context(user_factory, assign_roles):
    ops = user_factory(username="level_ops", first_name="Ops")
    assign_roles(ops, RoleSlug.OPS_MANAGER)

    regular = user_factory(username="level_regular", first_name="Regular")

    tech_high = user_factory(
        username="tech_high",
        first_name="High",
        level=EmployeeLevel.L2,
    )
    assign_roles(tech_high, RoleSlug.TECHNICIAN)

    tech_low = user_factory(
        username="tech_low",
        first_name="Low",
        level=EmployeeLevel.L2,
    )
    assign_roles(tech_low, RoleSlug.TECHNICIAN)

    now = datetime.now(tz=ZoneInfo("Asia/Tashkent"))
    _create_xp_entry(
        user_id=tech_high.id,
        amount=140,
        reference="level_control_high_xp",
        created_at=now - timedelta(days=2),
    )
    _create_xp_entry(
        user_id=tech_low.id,
        amount=25,
        reference="level_control_low_xp",
        created_at=now - timedelta(days=1),
    )

    return {
        "ops": ops,
        "regular": regular,
        "tech_high": tech_high,
        "tech_low": tech_low,
        "date_from": (now.date() - timedelta(days=6)).isoformat(),
        "date_to": now.date().isoformat(),
    }


def test_level_control_overview_requires_manager_role(
    authed_client_factory,
    level_control_context,
):
    client = authed_client_factory(level_control_context["regular"])
    response = client.get(LEVEL_OVERVIEW_URL)
    assert response.status_code == 403


def test_level_control_overview_returns_weekly_xp_rows(
    authed_client_factory,
    level_control_context,
):
    client = authed_client_factory(level_control_context["ops"])
    response = client.get(
        LEVEL_OVERVIEW_URL,
        {
            "date_from": level_control_context["date_from"],
            "date_to": level_control_context["date_to"],
        },
    )

    assert response.status_code == 200
    payload = response.data["data"]
    rows = payload["rows"]
    assert payload["weekly_target_xp"] == 100
    assert len(rows) >= 2

    by_user = {row["username"]: row for row in rows}
    assert by_user["tech_high"]["meets_target"] is True
    assert by_user["tech_low"]["meets_target"] is False
    assert by_user["tech_low"]["suggested_warning"] is True


def test_manual_level_set_creates_history_event(
    authed_client_factory,
    level_control_context,
):
    client = authed_client_factory(level_control_context["ops"])
    target_user = level_control_context["tech_low"]
    response = client.post(
        LEVEL_SET_URL_TEMPLATE.format(user_id=target_user.id),
        {
            "level": EmployeeLevel.L4,
            "note": "Escalated due special task",
            "clear_warning": True,
        },
        format="json",
    )

    assert response.status_code == 200
    target_user.refresh_from_db()
    assert target_user.level == EmployeeLevel.L4

    event = UserLevelHistoryEvent.objects.filter(user_id=target_user.id).order_by(
        "-created_at", "-id"
    ).first()
    assert event is not None
    assert event.source == "manual_override"
    assert event.actor_id == level_control_context["ops"].id
    assert event.new_level == EmployeeLevel.L4
    assert event.note == "Escalated due special task"


def test_level_control_user_history_includes_xp_and_level_events(
    authed_client_factory,
    level_control_context,
):
    client = authed_client_factory(level_control_context["ops"])
    target_user = level_control_context["tech_high"]
    client.post(
        LEVEL_SET_URL_TEMPLATE.format(user_id=target_user.id),
        {"level": EmployeeLevel.L3, "note": "promotion"},
        format="json",
    )

    response = client.get(
        LEVEL_HISTORY_URL_TEMPLATE.format(user_id=target_user.id),
        {
            "date_from": level_control_context["date_from"],
            "date_to": level_control_context["date_to"],
            "limit": 300,
        },
    )

    assert response.status_code == 200
    payload = response.data["data"]
    assert payload["user"]["id"] == target_user.id
    assert len(payload["xp_history"]) >= 1
    assert len(payload["level_history"]) >= 1
