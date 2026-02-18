from aiogram import BaseMiddleware
from django.utils import translation

from bot.etc.container import Container
from bot.etc.i18n import ensure_bot_locales_compiled, normalize_bot_locale


class I18nMiddleware(BaseMiddleware):
    def __init__(self, container: Container):
        self.container = container
        ensure_bot_locales_compiled()

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        locale = normalize_bot_locale(locale=getattr(user, "language_code", None))
        data["locale"] = locale
        with translation.override(locale):
            data["_"] = translation.gettext
            return await handler(event, data)
