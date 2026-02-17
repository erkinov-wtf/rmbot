from aiogram import Router

from bot.routers.technician_tickets.callbacks import router as callbacks_router
from bot.routers.technician_tickets.entry import router as entry_router

router = Router(name="technician_tickets")
router.include_router(entry_router)
router.include_router(callbacks_router)
