import asyncio

import pytest
from django.utils import timezone

from account.models import AccessRequest
from bot.routers.start import (
    XP_HISTORY_DEFAULT_LIMIT,
    _build_active_status_text,
    _build_pending_status_text,
    _build_xp_history_callback_data,
    _build_xp_history_pagination_markup,
    _build_xp_history_text,
    _build_xp_summary_text,
    _parse_xp_history_callback_data,
)
from core.utils.constants import RoleSlug

pytestmark = pytest.mark.django_db


def test_pending_status_text_contains_request_details():
    pending = AccessRequest.objects.create(
        telegram_id=990001,
        username="pending.tech",
        first_name="Pending",
        last_name="Tech",
        phone="+15550001111",
    )

    text = _build_pending_status_text(pending=pending, _=lambda value: value)

    assert "Your access request is under review" in text
    assert "Name: Pending Tech" in text
    assert "Username: @pending.tech" in text
    assert "Phone: +15550001111" in text
    assert "Submitted at:" in text
    assert "Request ID:" not in text


def test_active_status_text_for_technician_includes_queue_size(monkeypatch):
    class _DummyUser:
        id = 77
        first_name = "Status"
        last_name = "Tech"
        username = "status_tech"
        phone = "+15550002222"

        @staticmethod
        def get_level_display():
            return "L2"

    async def _stub_roles(*, user):
        del user
        return [RoleSlug.TECHNICIAN]

    async def _stub_active_ticket_count(*, technician_id: int):
        assert technician_id == 77
        return 3

    async def _stub_status_counts(*, technician_id: int):
        assert technician_id == 77
        return {
            "assigned": 1,
            "in_progress": 2,
            "waiting_qc": 4,
            "done": 9,
        }

    async def _stub_xp_totals(*, user_id: int):
        assert user_id == 77
        return 120, 6

    monkeypatch.setattr("bot.routers.start._active_role_slugs", _stub_roles)
    monkeypatch.setattr(
        "bot.routers.start._active_ticket_count_for_technician",
        _stub_active_ticket_count,
    )
    monkeypatch.setattr(
        "bot.routers.start._ticket_status_counts_for_technician",
        _stub_status_counts,
    )
    monkeypatch.setattr("bot.routers.start._xp_totals_for_user", _stub_xp_totals)

    text = asyncio.run(
        _build_active_status_text(user=_DummyUser(), _=lambda value: value)
    )

    assert "Your access is active" in text
    assert "Name: Status Tech" in text
    assert "Username: @status_tech" in text
    assert "Role: Technician" in text
    assert "XP balance: 120 points (6 updates)." in text
    assert "Open tickets: 3" in text
    assert "Waiting for quality check: 4" in text
    assert "Completed tickets: 9" in text


def test_xp_summary_text_contains_recent_entries(monkeypatch):
    class _DummyUser:
        id = 88

    class _Entry:
        def __init__(
            self,
            *,
            amount: int,
            entry_type: str,
            created_at,
            description: str = "",
        ):
            self.amount = amount
            self.entry_type = entry_type
            self.created_at = created_at
            self.description = description

    async def _stub_totals(*, user_id: int) -> tuple[int, int]:
        assert user_id == 88
        return 240, 4

    async def _stub_history(*, user_id: int, limit: int = 10, offset: int = 0):
        assert user_id == 88
        assert limit == 5
        assert offset == 0
        return [
            _Entry(
                amount=15,
                entry_type="ticket_base_xp",
                created_at=timezone.now(),
                description="Ticket completion base XP",
            )
        ]

    monkeypatch.setattr("bot.routers.start._xp_totals_for_user", _stub_totals)
    monkeypatch.setattr("bot.routers.start._xp_history_for_user", _stub_history)

    text = asyncio.run(_build_xp_summary_text(user=_DummyUser(), _=lambda v: v))

    assert "Your XP summary" in text
    assert "Total XP: 240" in text
    assert "Updates: 4" in text
    assert "Latest updates:" in text
    assert "+15 XP" in text
    assert "Reward for completing a ticket" in text


def test_xp_history_text_is_human_friendly(monkeypatch):
    class _DummyUser:
        id = 99

    class _Entry:
        def __init__(
            self,
            *,
            amount: int,
            entry_type: str,
            created_at,
            reference: str,
            description: str = "",
        ):
            self.amount = amount
            self.entry_type = entry_type
            self.created_at = created_at
            self.reference = reference
            self.description = description

    async def _stub_history(*, user_id: int, limit: int = 15, offset: int = 0):
        assert user_id == 99
        assert limit == XP_HISTORY_DEFAULT_LIMIT
        assert offset == 0
        return [
            _Entry(
                amount=7,
                entry_type="attendance_punctuality",
                created_at=timezone.now(),
                reference="attendance:99:2026-02-16",
                description="Attendance punctuality XP",
            )
        ]

    async def _stub_count(*, user_id: int):
        assert user_id == 99
        return 1

    monkeypatch.setattr("bot.routers.start._xp_history_for_user", _stub_history)
    monkeypatch.setattr("bot.routers.start._xp_history_count_for_user", _stub_count)

    text, total_count, limit, offset = asyncio.run(
        _build_xp_history_text(user=_DummyUser(), _=lambda v: v)
    )

    assert total_count == 1
    assert limit == XP_HISTORY_DEFAULT_LIMIT
    assert offset == 0
    assert "Your XP activity" in text
    assert "Showing 1-1 of 1 updates." in text
    assert "+7 XP" in text
    assert "On-time attendance reward" in text
    assert "attendance_punctuality" not in text
    assert "attendance:99:2026-02-16" not in text


def test_xp_history_callback_data_roundtrip():
    callback_data = _build_xp_history_callback_data(limit=15, offset=30)
    assert callback_data == "xph:15:30"
    assert _parse_xp_history_callback_data(callback_data=callback_data) == (15, 30)


def test_xp_history_callback_data_rejects_invalid_payload():
    assert _parse_xp_history_callback_data(callback_data="xph:bad:10") is None
    assert _parse_xp_history_callback_data(callback_data="xph:10:-1") is None
    assert _parse_xp_history_callback_data(callback_data="oops:10:0") is None


def test_xp_history_pagination_markup_has_nav_buttons():
    markup = _build_xp_history_pagination_markup(
        total_count=25,
        limit=10,
        offset=10,
        _=lambda value: value,
    )
    assert markup is not None
    assert [button.text for button in markup.inline_keyboard[0]] == [
        "⬅ Previous",
        "Next ➡",
    ]
