from aiogram import Router

from bot.routers.start.access import router as start_access_router
from bot.routers.start.profile import router as start_profile_router
from bot.routers.start.xp import router as start_xp_router

router = Router(name="start")
router.include_router(start_access_router)
router.include_router(start_profile_router)
router.include_router(start_xp_router)
