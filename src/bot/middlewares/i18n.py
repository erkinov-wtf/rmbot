from aiogram import BaseMiddleware
from django.utils import translation

from bot.etc.container import Container
from bot.etc.i18n import normalize_bot_locale


class I18nMiddleware(BaseMiddleware):
    def __init__(self, container: Container):
        self.container = container

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        locale = normalize_bot_locale(
            locale=getattr(user, "language_code", None),
            default_locale=self.container.settings.default_locale,
            fallback_locale=self.container.settings.fallback_locale,
        )
        data["locale"] = locale
        with translation.override(locale):
            data["_"] = translation.gettext
            return await handler(event, data)
