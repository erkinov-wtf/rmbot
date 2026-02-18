from __future__ import annotations

import logging
import subprocess
from pathlib import Path

SUPPORTED_BOT_LOCALES = ("en", "ru", "uz")
BOT_LOCALE_FALLBACK = "uz"

logger = logging.getLogger(__name__)
_LOCALES_COMPILE_ATTEMPTED = False


def _normalize_locale_token(raw: str | None) -> str | None:
    if not raw:
        return None
    normalized = str(raw).strip().lower().replace("_", "-")
    if not normalized:
        return None
    return normalized.split("-", 1)[0]


def normalize_bot_locale(
    *,
    locale: str | None,
    default_locale: str = BOT_LOCALE_FALLBACK,
    fallback_locale: str = BOT_LOCALE_FALLBACK,
) -> str:
    # Telegram locale is authoritative; if unsupported, fallback is always Uzbek.
    del default_locale, fallback_locale
    normalized = _normalize_locale_token(locale)
    if normalized in SUPPORTED_BOT_LOCALES:
        return normalized
    return BOT_LOCALE_FALLBACK


def _src_dir() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_bot_locales_compiled() -> None:
    global _LOCALES_COMPILE_ATTEMPTED

    if _LOCALES_COMPILE_ATTEMPTED:
        return
    _LOCALES_COMPILE_ATTEMPTED = True

    locale_root = _src_dir() / "locales"
    for locale in SUPPORTED_BOT_LOCALES:
        po_path = locale_root / locale / "LC_MESSAGES" / "django.po"
        mo_path = locale_root / locale / "LC_MESSAGES" / "django.mo"
        if not po_path.exists():
            continue
        if mo_path.exists() and mo_path.stat().st_mtime >= po_path.stat().st_mtime:
            continue

        try:
            subprocess.run(
                ["msgfmt", str(po_path), "-o", str(mo_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            logger.warning(
                "msgfmt is not available. Bot translations may fall back to source text."
            )
            return
        except subprocess.CalledProcessError as exc:
            logger.warning(
                "Failed to compile locale %s (%s): %s",
                locale,
                po_path,
                (exc.stderr or exc.stdout or "").strip(),
            )
