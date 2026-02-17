from aiogram import Router

from bot.routers.ticket_admin_create import router as ticket_admin_create_router
from bot.routers.ticket_admin_review import router as ticket_admin_review_router

router = Router(name="ticket_admin")
router.include_router(ticket_admin_create_router)
router.include_router(ticket_admin_review_router)
