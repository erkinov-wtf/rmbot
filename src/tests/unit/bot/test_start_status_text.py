import asyncio

import pytest
from django.utils import timezone

from account.models import AccessRequest
from bot.routers.start import (
    _build_active_status_text,
    _build_pending_status_text,
    _build_xp_history_text,
    _build_xp_summary_text,
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

    assert "Access status: pending" in text
    assert "Name: Pending Tech" in text
    assert "Username: @pending.tech" in text
    assert "Phone: +15550001111" in text
    assert f"Request ID: {pending.id}" in text


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

    assert "Access status: active" in text
    assert "Name: Status Tech" in text
    assert "Username: @status_tech" in text
    assert "Roles: technician" in text
    assert "Total XP: 120 (transactions: 6)" in text
    assert "Active tickets in queue: 3" in text
    assert "Waiting QC tickets: 4" in text
    assert "Done tickets: 9" in text


def test_xp_summary_text_contains_recent_entries(monkeypatch):
    class _DummyUser:
        id = 88

    class _Entry:
        def __init__(self, *, amount: int, entry_type: str, created_at):
            self.amount = amount
            self.entry_type = entry_type
            self.created_at = created_at

    async def _stub_totals(*, user_id: int):
        assert user_id == 88
        return 240, 4

    async def _stub_history(*, user_id: int, limit: int = 10):
        assert user_id == 88
        assert limit == 5
        return [
            _Entry(
                amount=15,
                entry_type="ticket_base_xp",
                created_at=timezone.now(),
            )
        ]

    monkeypatch.setattr("bot.routers.start._xp_totals_for_user", _stub_totals)
    monkeypatch.setattr("bot.routers.start._xp_history_for_user", _stub_history)

    text = asyncio.run(_build_xp_summary_text(user=_DummyUser(), _=lambda v: v))

    assert "XP summary" in text
    assert "Total XP: 240" in text
    assert "Transactions: 4" in text
    assert "Recent transactions:" in text
    assert "| +15 | ticket_base_xp" in text


def test_xp_history_text_contains_references(monkeypatch):
    class _DummyUser:
        id = 99

    class _Entry:
        def __init__(self, *, amount: int, entry_type: str, created_at, reference: str):
            self.amount = amount
            self.entry_type = entry_type
            self.created_at = created_at
            self.reference = reference

    async def _stub_history(*, user_id: int, limit: int = 15):
        assert user_id == 99
        assert limit == 15
        return [
            _Entry(
                amount=7,
                entry_type="attendance_punctuality",
                created_at=timezone.now(),
                reference="attendance:99:2026-02-16",
            )
        ]

    monkeypatch.setattr("bot.routers.start._xp_history_for_user", _stub_history)

    text = asyncio.run(_build_xp_history_text(user=_DummyUser(), _=lambda v: v))

    assert "XP transaction history" in text
    assert "| +7 | attendance_punctuality | attendance:99:2026-02-16" in text
