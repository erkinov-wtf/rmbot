import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from core.utils.telegram import InitDataValidationError, validate_init_data


def _build_init_data(
    bot_token: str, user_payload: dict, auth_date: int | None = None
) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return urlencode(data)


def test_invalid_hash_raises():
    auth_date = int(time.time())
    bad_init = f"auth_date={auth_date}&hash=invalid"

    with pytest.raises(InitDataValidationError):
        validate_init_data(bad_init, bot_token="token")


def test_valid_init_data_returns_payload():
    init_data = _build_init_data(
        bot_token="token",
        user_payload={"id": 123, "username": "alice"},
    )

    parsed = validate_init_data(init_data, bot_token="token")

    assert "user" in parsed
    assert "auth_date" in parsed


def test_expired_init_data_raises():
    old_ts = int(time.time()) - 1000
    init_data = _build_init_data(
        bot_token="token",
        user_payload={"id": 123},
        auth_date=old_ts,
    )

    with pytest.raises(InitDataValidationError):
        validate_init_data(init_data, bot_token="token", max_age_seconds=300)


def test_future_auth_date_beyond_skew_raises():
    future_ts = int(time.time()) + 120
    init_data = _build_init_data(
        bot_token="token",
        user_payload={"id": 123},
        auth_date=future_ts,
    )

    with pytest.raises(InitDataValidationError):
        validate_init_data(
            init_data,
            bot_token="token",
            max_future_skew_seconds=30,
        )


def test_future_auth_date_within_skew_is_valid():
    future_ts = int(time.time()) + 5
    init_data = _build_init_data(
        bot_token="token",
        user_payload={"id": 123},
        auth_date=future_ts,
    )

    parsed = validate_init_data(
        init_data,
        bot_token="token",
        max_future_skew_seconds=30,
    )

    assert parsed["auth_date"] == str(future_ts)
