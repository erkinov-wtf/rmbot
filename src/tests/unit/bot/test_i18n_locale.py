import asyncio
from types import SimpleNamespace

from bot.config import BotSettings
from bot.etc.container import Container
from bot.etc.i18n import normalize_bot_locale
from bot.middlewares.i18n import I18nMiddleware


def _settings() -> BotSettings:
    return BotSettings(
        token="",
        mode="polling",
        webhook_base_url="",
        webhook_path="/bot/webhook/",
        webhook_secret="",
        parse_mode="HTML",
        default_locale="en",
        fallback_locale="en",
    )


def test_normalize_bot_locale_uses_supported_telegram_base_locale():
    assert normalize_bot_locale(locale="ru-RU") == "ru"
    assert normalize_bot_locale(locale="en_US") == "en"
    assert normalize_bot_locale(locale="uz") == "uz"


def test_normalize_bot_locale_falls_back_to_uz_when_unsupported_or_missing():
    assert normalize_bot_locale(locale="de-DE") == "uz"
    assert normalize_bot_locale(locale=None) == "uz"


def test_i18n_middleware_uses_telegram_locale_for_each_request():
    middleware = I18nMiddleware(container=Container(settings=_settings()))

    async def handler(_event, data):
        translate = data["_"]
        return data["locale"], translate("Unknown command. Use /help.")

    locale_ru, translated_ru = asyncio.run(
        middleware.__call__(
            handler,
            object(),
            {"event_from_user": SimpleNamespace(language_code="ru-RU")},
        )
    )
    locale_fallback, translated_fallback = asyncio.run(
        middleware.__call__(
            handler,
            object(),
            {"event_from_user": SimpleNamespace(language_code="de-DE")},
        )
    )

    assert locale_ru == "ru"
    assert isinstance(translated_ru, str)
    assert translated_ru

    assert locale_fallback == "uz"
    assert isinstance(translated_fallback, str)
    assert translated_fallback
