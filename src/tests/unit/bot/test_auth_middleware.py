import asyncio
from types import SimpleNamespace

import pytest

from account.models import TelegramProfile
from account.services import AccountService
from bot.middlewares.auth import AuthMiddleware

pytestmark = pytest.mark.django_db


async def _run_sync_passthrough(func, *args, **kwargs):
    return func(*args, **kwargs)


def test_auth_middleware_uses_event_from_user_context(user_factory, monkeypatch):
    user = user_factory(username="tech_event_ctx", first_name="Tech", is_active=True)
    profile = TelegramProfile.objects.create(
        telegram_id=910001,
        user=user,
        username="tech_event_ctx",
        first_name="Tech",
    )
    middleware = AuthMiddleware()
    monkeypatch.setattr("bot.middlewares.auth.run_sync", _run_sync_passthrough)
    monkeypatch.setattr(
        AccountService,
        "get_active_profile",
        staticmethod(lambda _telegram_id: profile),
    )

    async def handler(_event, data):
        return data.get("user"), data.get("telegram_profile")

    resolved_user, resolved_profile = asyncio.run(
        middleware.__call__(
            handler,
            object(),
            {"event_from_user": SimpleNamespace(id=910001)},
        )
    )

    assert resolved_user is not None
    assert resolved_profile is not None
    assert resolved_user.id == user.id
    assert resolved_profile.id == profile.id


def test_auth_middleware_falls_back_to_event_from_user_attribute(
    user_factory,
    monkeypatch,
):
    user = user_factory(username="tech_event_attr", first_name="Tech", is_active=True)
    profile = TelegramProfile.objects.create(
        telegram_id=910002,
        user=user,
        username="tech_event_attr",
        first_name="Tech",
    )
    middleware = AuthMiddleware()
    monkeypatch.setattr("bot.middlewares.auth.run_sync", _run_sync_passthrough)
    monkeypatch.setattr(
        AccountService,
        "get_active_profile",
        staticmethod(lambda _telegram_id: profile),
    )

    async def handler(_event, data):
        return data.get("user"), data.get("telegram_profile")

    event = SimpleNamespace(from_user=SimpleNamespace(id=910002))
    resolved_user, resolved_profile = asyncio.run(
        middleware.__call__(
            handler,
            event,
            {},
        )
    )

    assert resolved_user is not None
    assert resolved_profile is not None
    assert resolved_user.id == user.id
    assert resolved_profile.id == profile.id
