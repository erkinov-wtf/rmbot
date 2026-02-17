from aiogram import Router

from bot.routers.ticket_admin.review_callbacks import router as review_callbacks_router
from bot.routers.ticket_admin.review_entry import router as review_entry_router

router = Router(name="ticket_admin_review")
router.include_router(review_entry_router)
router.include_router(review_callbacks_router)
