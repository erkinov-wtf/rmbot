from aiogram import BaseMiddleware

from account.services import AccountService
from core.utils.asyncio import run_sync


class AuthMiddleware(BaseMiddleware):
    @staticmethod
    def _resolve_from_user(event, data):
        from aiogram.types import CallbackQuery, Message

        # Update-level middlewares receive Update events; aiogram exposes actor
        # user in the shared data payload as `event_from_user`.
        from_user = data.get("event_from_user")
        if from_user:
            return from_user

        message = None
        if isinstance(event, Message):
            message = event
        elif isinstance(event, CallbackQuery):
            message = event.message

        return getattr(event, "from_user", None) or getattr(message, "from_user", None)

    async def __call__(self, handler, event, data):
        from_user = self._resolve_from_user(event, data)
        if not from_user:
            return await handler(event, data)

        profile = await run_sync(AccountService.get_active_profile, from_user.id)
        data["telegram_profile"] = profile
        data["user"] = profile.user if profile else None
        return await handler(event, data)
