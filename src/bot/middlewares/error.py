from logging import getLogger
from typing import TYPE_CHECKING, Optional

from aiogram import BaseMiddleware
from django.utils.translation import gettext_noop

logger = getLogger(__name__)
ERROR_GENERIC_MESSAGE = gettext_noop("Something went wrong. Please try again later.")

if TYPE_CHECKING:
    from aiogram.types import Message


class ErrorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):

        try:
            return await handler(event, data)
        except Exception as e:
            logger.exception(f"Unhandled bot exception: {e}")

            message = self._get_message(event)

            if message:
                translate = data.get("_", lambda x: x)
                await message.answer(translate(ERROR_GENERIC_MESSAGE))

            return None

    @staticmethod
    def _get_message(event) -> Optional["Message"]:
        from aiogram.types import CallbackQuery, Message

        if isinstance(event, Message):
            return event
        elif isinstance(event, CallbackQuery):
            return event.message
        return None
