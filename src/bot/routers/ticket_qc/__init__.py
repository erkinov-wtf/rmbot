from aiogram import Router

from bot.routers.ticket_qc.callbacks import router as callbacks_router
from bot.routers.ticket_qc.entry import router as entry_router

router = Router(name="ticket_qc")
router.include_router(entry_router)
router.include_router(callbacks_router)
