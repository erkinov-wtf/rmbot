import hashlib
import hmac
import time
import urllib.parse
from typing import Any


class InitDataValidationError(ValueError):
    pass


def _build_data_check_string(data: dict[str, str]) -> str:
    return "\n".join(f"{k}={v}" for k, v in sorted(data.items()))


def extract_init_data_hash(init_data: str) -> str:
    if not init_data:
        raise InitDataValidationError("init_data is required")

    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise InitDataValidationError("init_data is invalid") from exc

    provided_hash = parsed.get("hash")
    if not provided_hash:
        raise InitDataValidationError("hash is missing in init_data")

    return provided_hash


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 300,
    max_future_skew_seconds: int = 30,
) -> dict[str, Any]:
    """
    Validate Telegram Mini App initData according to Telegram spec.

    Args:
        init_data: Raw query string from Telegram Mini App (window.Telegram.WebApp.initData)
        bot_token: Bot token used to derive secret key
        max_age_seconds: Allowed age for auth_date

    Returns:
        Parsed dict of init data (excluding hash) on success.

    Raises:
        InitDataValidationError: when hash or auth_date is invalid
    """
    if not init_data:
        raise InitDataValidationError("init_data is required")

    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    except ValueError as exc:
        raise InitDataValidationError("init_data is invalid") from exc

    provided_hash = parsed.pop("hash", None)
    if not provided_hash:
        raise InitDataValidationError("hash is missing in init_data")

    data_check_string = _build_data_check_string(parsed)
    # Telegram Mini Apps spec:
    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, provided_hash):
        raise InitDataValidationError("Invalid init_data hash")

    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except (TypeError, ValueError):
        raise InitDataValidationError("auth_date is missing or invalid") from None

    now_ts = int(time.time())
    if auth_date <= 0:
        raise InitDataValidationError("auth_date is missing or invalid")
    if auth_date > (now_ts + max_future_skew_seconds):
        raise InitDataValidationError("init_data auth_date is in the future")
    if (now_ts - auth_date) > max_age_seconds:
        raise InitDataValidationError("init_data is expired")

    return parsed
