from aiogram import BaseMiddleware

from account.services import get_active_profile
from core.utils.asyncio import run_sync


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        from aiogram.types import CallbackQuery, Message

        message = None
        if isinstance(event, Message):
            message = event
        elif isinstance(event, CallbackQuery):
            message = event.message

        from_user = getattr(message, "from_user", None)
        if not from_user:
            return await handler(event, data)

        profile = await run_sync(get_active_profile, from_user.id)
        data["telegram_profile"] = profile
        data["user"] = profile.user if profile else None
        return await handler(event, data)
