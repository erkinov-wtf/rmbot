from aiogram import Router


class BotRouterRegistry:
    """Builds and wires the aiogram root router with all feature routers."""

    @staticmethod
    def build() -> Router:
        from bot.routers import (
            fallback,
            start,
            technician_tickets,
        )

        root = Router(name="root")
        root.include_router(start.router)
        root.include_router(technician_tickets.router)
        root.include_router(fallback.router)
        return root


def setup_routers() -> Router:
    return BotRouterRegistry.build()
