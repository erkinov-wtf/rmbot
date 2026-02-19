from logging import getLogger
from urllib.parse import urlparse

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo
from django.utils import translation
from django.utils.translation import gettext_noop

from bot.etc.i18n import normalize_bot_locale
from bot.config import get_bot_settings
from bot.runtime import close_bundle, get_bundle

logger = getLogger(__name__)
NATIVE_MINIAPP_MENU_TEXT = gettext_noop("Open Mini App")


def _is_valid_https_webapp_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


async def configure_native_menu_button(
    *,
    bundle=None,
    settings_obj=None,
) -> None:
    settings = settings_obj or get_bot_settings()
    bundle = bundle or await get_bundle()
    miniapp_url = str(settings.miniapp_url or "").strip()
    with translation.override(normalize_bot_locale(locale=settings.default_locale)):
        menu_text = translation.gettext(NATIVE_MINIAPP_MENU_TEXT)
    if miniapp_url and _is_valid_https_webapp_url(miniapp_url):
        try:
            await bundle.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text=menu_text,
                    web_app=WebAppInfo(url=miniapp_url),
                ),
            )
            logger.info("Configured native Telegram menu button for mini app.")
            return
        except TelegramBadRequest:
            logger.exception(
                "Could not configure mini app menu button for URL: %s. Falling back to commands menu button.",
                miniapp_url,
            )
    elif miniapp_url:
        logger.warning(
            "BOT_MINIAPP_URL is not a valid HTTPS URL (%s). Falling back to commands menu button.",
            miniapp_url,
        )

    await bundle.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    logger.info("Configured native Telegram menu button for commands.")


async def start_polling() -> None:
    bundle = await get_bundle()
    await configure_native_menu_button(bundle=bundle)
    logger.info("Starting bot in polling mode")
    await bundle.dispatcher.start_polling(
        bundle.bot,
        allowed_updates=bundle.dispatcher.resolve_used_update_types(),
    )


async def setup_webhook(drop_pending_updates: bool = False) -> None:
    settings = get_bot_settings()
    bundle = await get_bundle()
    await configure_native_menu_button(bundle=bundle, settings_obj=settings)
    await bundle.bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret or None,
        drop_pending_updates=drop_pending_updates,
    )
    logger.info("Webhook configured: %s", settings.webhook_url)


async def remove_webhook(drop_pending_updates: bool = False) -> None:
    bundle = await get_bundle()
    await bundle.bot.delete_webhook(drop_pending_updates=drop_pending_updates)
    logger.info("Webhook deleted")


async def shutdown() -> None:
    await close_bundle()
