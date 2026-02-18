import asyncio
from types import SimpleNamespace

import pytest

from account.services import AccountService
from bot.routers.start.profile import StartProfileSupportMixin

pytestmark = pytest.mark.django_db


class _DummyState:
    @staticmethod
    async def get_state():
        return None

    @staticmethod
    async def clear():
        return None


class _DummyMessage:
    def __init__(self, telegram_id: int) -> None:
        self.from_user = SimpleNamespace(id=telegram_id)
        self.answers: list[dict[str, object]] = []

    async def answer(self, text: str, reply_markup=None):
        self.answers.append({"text": text, "reply_markup": reply_markup})


def test_help_hides_start_access_button_for_pending_request(monkeypatch):
    captured: dict[str, bool] = {}

    async def _main_menu_stub(*, user, include_start_access=False, _=None):
        del user, _
        captured["include_start_access"] = include_start_access
        return "MARKUP"

    monkeypatch.setattr(
        AccountService,
        "get_pending_access_request",
        staticmethod(lambda _telegram_id: object()),
    )
    monkeypatch.setattr(
        "bot.routers.start.profile.BotMenuService.main_menu_markup_for_user",
        _main_menu_stub,
    )

    message = _DummyMessage(telegram_id=880001)

    asyncio.run(
        StartProfileSupportMixin.handle_help(
            message=message,
            _=lambda value: value,
            user=None,
            telegram_profile=None,
            state=_DummyState(),
        )
    )

    assert captured["include_start_access"] is False
    assert message.answers[-1]["reply_markup"] == "MARKUP"
    help_text = str(message.answers[-1]["text"])
    assert "<b>Help</b>" in help_text
    assert "<code>/start</code>" in help_text
    assert "Check your request status" in help_text
    assert "Start access request" not in help_text


def test_help_shows_start_access_button_for_unregistered_user(monkeypatch):
    captured: dict[str, bool] = {}

    async def _main_menu_stub(*, user, include_start_access=False, _=None):
        del user, _
        captured["include_start_access"] = include_start_access
        return "MARKUP"

    monkeypatch.setattr(
        AccountService,
        "get_pending_access_request",
        staticmethod(lambda _telegram_id: None),
    )
    monkeypatch.setattr(
        "bot.routers.start.profile.BotMenuService.main_menu_markup_for_user",
        _main_menu_stub,
    )

    message = _DummyMessage(telegram_id=880002)

    asyncio.run(
        StartProfileSupportMixin.handle_help(
            message=message,
            _=lambda value: value,
            user=None,
            telegram_profile=None,
            state=_DummyState(),
        )
    )

    assert captured["include_start_access"] is True
    help_text = str(message.answers[-1]["text"])
    assert "<code>/start</code>" in help_text
    assert "Start access request" in help_text


def test_help_hides_start_access_button_for_active_user(user_factory, monkeypatch):
    user = user_factory(
        username="active_help_user", first_name="Active", is_active=True
    )
    captured: dict[str, bool] = {}

    async def _main_menu_stub(*, user, include_start_access=False, _=None):
        del user, _
        captured["include_start_access"] = include_start_access
        return "MARKUP"

    monkeypatch.setattr(
        AccountService,
        "get_pending_access_request",
        staticmethod(lambda _telegram_id: None),
    )
    monkeypatch.setattr(
        "bot.routers.start.profile.BotMenuService.main_menu_markup_for_user",
        _main_menu_stub,
    )

    message = _DummyMessage(telegram_id=880003)

    asyncio.run(
        StartProfileSupportMixin.handle_help(
            message=message,
            _=lambda value: value,
            user=user,
            telegram_profile=None,
            state=_DummyState(),
        )
    )

    assert captured["include_start_access"] is False
    help_text = str(message.answers[-1]["text"])
    assert "<code>/start</code>" not in help_text


def test_help_text_includes_technician_commands_and_excludes_ticket_admin_qc():
    text = StartProfileSupportMixin.build_help_text(
        include_start_access=False,
        has_pending_request=False,
        is_active_user=True,
        is_technician=True,
        can_create_ticket=True,
        can_open_review_panel=True,
        can_qc_checks=True,
        _=lambda value: value,
    )

    assert "<b>Technician</b>" in text
    assert "<code>/queue</code>" in text
    assert "<code>/xp_history</code>" in text
    assert "<b>Ticket Admin</b>" not in text
    assert "<code>/ticket_create</code>" not in text
    assert "<code>/ticket_review</code>" not in text
    assert "<b>QC</b>" not in text
    assert "<code>/qc_checks</code>" not in text
    assert "Telegram Mini App" in text
