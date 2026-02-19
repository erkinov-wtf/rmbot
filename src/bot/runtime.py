import asyncio
from logging import getLogger

from bot.etc.loader import BotBundle, create_bot_bundle

_bundle: BotBundle | None = None
_lock = asyncio.Lock()
logger = getLogger(__name__)


async def get_bundle() -> BotBundle:
    global _bundle
    if _bundle is not None:
        return _bundle

    async with _lock:
        if _bundle is None:
            _bundle = create_bot_bundle()
    return _bundle


async def close_bundle() -> None:
    global _bundle
    if _bundle is None:
        return
    try:
        await _bundle.storage.close()
    except Exception:
        logger.exception("Failed to close bot FSM storage.")
    try:
        await _bundle.bot.session.close()
    finally:
        _bundle = None
