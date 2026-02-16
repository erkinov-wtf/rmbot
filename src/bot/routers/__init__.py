from aiogram import Router

from bot.routers import fallback, start, technician_tickets


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(start.router)
    root.include_router(technician_tickets.router)
    root.include_router(fallback.router)
    return root
