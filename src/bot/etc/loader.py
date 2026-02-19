from dataclasses import dataclass
from logging import getLogger

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import BotSettings, get_bot_settings
from bot.etc.container import Container
from bot.etc.i18n import ensure_bot_locales_compiled
from bot.middlewares import (
    AuthMiddleware,
    DIMiddleware,
    ErrorMiddleware,
    I18nMiddleware,
)
from bot.url_router import get_root_router

logger = getLogger(__name__)


@dataclass
class BotBundle:
    bot: Bot
    dispatcher: Dispatcher
    container: Container
    storage: BaseStorage


def _resolve_fsm_storage(settings: BotSettings) -> BaseStorage:
    storage_backend = settings.fsm_storage.strip().lower()
    if storage_backend == "memory":
        return MemoryStorage()
    if storage_backend == "redis":
        redis_url = settings.fsm_redis_url.strip()
        if not redis_url:
            raise RuntimeError(
                "BOT_FSM_REDIS_URL is required when BOT_FSM_STORAGE='redis'."
            )
        return RedisStorage.from_url(redis_url)
    raise RuntimeError(
        f"Unsupported BOT_FSM_STORAGE='{settings.fsm_storage}'. "
        "Use 'memory' or 'redis'."
    )


def create_bot_bundle() -> BotBundle:
    settings = get_bot_settings()
    ensure_bot_locales_compiled()
    parse_mode_key = settings.parse_mode.strip().upper().replace("-", "_")
    parse_mode_key = "MARKDOWN_V2" if parse_mode_key == "MARKDOWNV2" else parse_mode_key
    parse_mode = ParseMode.__members__.get(parse_mode_key, ParseMode.HTML)
    bot = Bot(token=settings.token, default=DefaultBotProperties(parse_mode=parse_mode))
    container = Container(settings=settings)
    storage = _resolve_fsm_storage(settings)
    logger.info("Bot FSM storage backend: %s", settings.fsm_storage.strip().lower())

    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.outer_middleware(ErrorMiddleware())
    dispatcher.update.middleware(I18nMiddleware(container=container))
    dispatcher.update.middleware(DIMiddleware(container=container))
    dispatcher.update.middleware(AuthMiddleware())
    dispatcher.include_router(get_root_router())

    return BotBundle(
        bot=bot,
        dispatcher=dispatcher,
        container=container,
        storage=storage,
    )
