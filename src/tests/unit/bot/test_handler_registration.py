from aiogram.handlers import BaseHandler

from bot.routers import setup_routers


def _iter_routers(router):
    yield router
    for child in router.sub_routers:
        yield from _iter_routers(child)


def test_bot_router_uses_class_based_handlers_only():
    root_router = setup_routers()
    violations: list[str] = []

    for router in _iter_routers(root_router):
        for event_name, observer in router.observers.items():
            for registered_handler in observer.handlers:
                callback = registered_handler.callback
                if isinstance(callback, type) and issubclass(callback, BaseHandler):
                    continue
                violations.append(f"{router.name}:{event_name}:{callback}")

    assert violations == []
