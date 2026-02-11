import gettext
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=128)
def _resolve_translation(
    domain: str, locales_path: str, locale: str
) -> gettext.NullTranslations:
    return gettext.translation(
        domain,
        localedir=locales_path,
        languages=[locale],
        fallback=True,
    )


class Translator:
    def __init__(
        self, locales_path: Path, domain: str = "bot", fallback_locale: str = "en"
    ):
        self.locales_path = locales_path
        self.domain = domain
        self.fallback_locale = fallback_locale

    def _translation(self, locale: str) -> gettext.NullTranslations:
        return _resolve_translation(self.domain, str(self.locales_path), locale)

    def gettext(self, locale: str) -> Callable[[str], str]:
        translation = self._translation(locale or self.fallback_locale)
        return translation.gettext
