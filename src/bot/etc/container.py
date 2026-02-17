from logging import getLogger

from bot.config import BotSettings

logger = getLogger(__name__)


class Container:
    def __init__(self, settings: BotSettings):
        self.settings = settings
        self.logger = logger
