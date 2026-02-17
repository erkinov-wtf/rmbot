from aiogram import Router

from bot.routers.ticket_admin.create_callbacks import (
    router as ticket_admin_create_callbacks_router,
)
from bot.routers.ticket_admin.create_entry import (
    router as ticket_admin_create_entrypoints_router,
)

router = Router(name="ticket_admin_create")
router.include_router(ticket_admin_create_entrypoints_router)
router.include_router(ticket_admin_create_callbacks_router)
