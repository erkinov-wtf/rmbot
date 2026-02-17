SUPPORTED_BOT_LOCALES = {"en", "ru", "uz"}


def normalize_bot_locale(
    *,
    locale: str | None,
    default_locale: str = "en",
    fallback_locale: str = "en",
) -> str:
    candidates = [locale, default_locale, fallback_locale, "en"]
    for raw in candidates:
        if not raw:
            continue
        normalized = str(raw).strip().lower().replace("_", "-")
        if not normalized:
            continue
        base = normalized.split("-", 1)[0]
        if base in SUPPORTED_BOT_LOCALES:
            return base
    return "en"
