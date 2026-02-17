from aiogram import Router

from bot.routers import fallback, start, technician_tickets, ticket_admin, ticket_qc


class BotRouterRegistry:
    """Builds and wires the aiogram root router with all feature routers."""

    @staticmethod
    def build() -> Router:
        root = Router(name="root")
        root.include_router(start.router)
        root.include_router(technician_tickets.router)
        root.include_router(ticket_admin.router)
        root.include_router(ticket_qc.router)
        root.include_router(fallback.router)
        return root


def setup_routers() -> Router:
    return BotRouterRegistry.build()
