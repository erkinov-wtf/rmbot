from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class BotSettings:
    token: str
    mode: str
    webhook_base_url: str
    webhook_path: str
    webhook_secret: str
    miniapp_url: str
    parse_mode: str
    default_locale: str
    fallback_locale: str
    fsm_storage: str
    fsm_redis_url: str

    @property
    def webhook_url(self) -> str:
        base = self.webhook_base_url.rstrip("/")
        path = (
            self.webhook_path
            if self.webhook_path.startswith("/")
            else f"/{self.webhook_path}"
        )
        return f"{base}{path}"


def get_bot_settings() -> BotSettings:
    return BotSettings(
        token=settings.BOT_TOKEN,
        mode=settings.BOT_MODE,
        webhook_base_url=settings.BOT_WEBHOOK_BASE_URL,
        webhook_path=settings.BOT_WEBHOOK_PATH,
        webhook_secret=settings.BOT_WEBHOOK_SECRET,
        miniapp_url=settings.BOT_MINIAPP_URL,
        parse_mode=settings.BOT_PARSE_MODE,
        default_locale=settings.BOT_DEFAULT_LOCALE,
        fallback_locale=settings.BOT_FALLBACK_LOCALE,
        fsm_storage=settings.BOT_FSM_STORAGE,
        fsm_redis_url=settings.BOT_FSM_REDIS_URL,
    )
