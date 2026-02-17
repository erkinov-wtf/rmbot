from typing import Any

from aiogram import F, Router
from aiogram.handlers import MessageHandler

router = Router(name="fallback")


@router.message(F.text, F.text.startswith("/"))
class UnknownCommandHandler(MessageHandler):
    async def handle(self) -> Any:
        _ = self.data["_"]
        await self.event.answer(_("⚠️ <b>Unknown command.</b>\nUse <code>/help</code>."))
