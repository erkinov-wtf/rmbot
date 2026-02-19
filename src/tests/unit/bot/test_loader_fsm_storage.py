from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import BotSettings
from bot.etc import loader


def _build_settings(**overrides) -> BotSettings:
    payload = {
        "token": "token",
        "mode": "polling",
        "webhook_base_url": "https://example.com",
        "webhook_path": "bot/webhook/",
        "webhook_secret": "",
        "miniapp_url": "https://example.com/miniapp",
        "parse_mode": "HTML",
        "default_locale": "uz",
        "fallback_locale": "uz",
        "fsm_storage": "memory",
        "fsm_redis_url": "redis://localhost:6379/0",
    }
    payload.update(overrides)
    return BotSettings(**payload)


def test_resolve_fsm_storage_memory_backend():
    settings = _build_settings(fsm_storage="memory")
    storage = loader._resolve_fsm_storage(settings)
    assert isinstance(storage, MemoryStorage)


def test_resolve_fsm_storage_redis_backend(monkeypatch):
    settings = _build_settings(
        fsm_storage="redis",
        fsm_redis_url="redis://redis:6379/5",
    )
    sentinel_storage = object()
    captured_url = {"value": None}

    def _fake_from_url(cls, redis_url: str):
        captured_url["value"] = redis_url
        return sentinel_storage

    monkeypatch.setattr(
        loader.RedisStorage,
        "from_url",
        classmethod(_fake_from_url),
    )

    storage = loader._resolve_fsm_storage(settings)

    assert storage is sentinel_storage
    assert captured_url["value"] == "redis://redis:6379/5"


def test_resolve_fsm_storage_rejects_unknown_backend():
    settings = _build_settings(fsm_storage="broken")

    try:
        loader._resolve_fsm_storage(settings)
    except RuntimeError as exc:
        assert "Unsupported BOT_FSM_STORAGE='broken'" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for invalid BOT_FSM_STORAGE.")


def test_resolve_fsm_storage_requires_redis_url():
    settings = _build_settings(fsm_storage="redis", fsm_redis_url="  ")

    try:
        loader._resolve_fsm_storage(settings)
    except RuntimeError as exc:
        assert "BOT_FSM_REDIS_URL is required" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when redis URL is empty.")
