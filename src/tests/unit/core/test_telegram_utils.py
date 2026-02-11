import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from django.test import SimpleTestCase

from core.utils.telegram import InitDataValidationError, validate_init_data


def _build_init_data(bot_token: str, user_payload: dict, auth_date: int | None = None) -> str:
    data = {
        "user": json.dumps(user_payload, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


class ValidateInitDataTests(SimpleTestCase):
    def test_invalid_hash_raises(self):
        auth_date = int(time.time())
        bad_init = f"auth_date={auth_date}&hash=invalid"
        with self.assertRaises(InitDataValidationError):
            validate_init_data(bad_init, bot_token="token")

    def test_valid_init_data_returns_payload(self):
        init_data = _build_init_data(
            bot_token="token",
            user_payload={"id": 123, "username": "alice"},
        )
        parsed = validate_init_data(init_data, bot_token="token")
        self.assertIn("user", parsed)
        self.assertIn("auth_date", parsed)

    def test_expired_init_data_raises(self):
        old_ts = int(time.time()) - 1000
        init_data = _build_init_data(
            bot_token="token",
            user_payload={"id": 123},
            auth_date=old_ts,
        )
        with self.assertRaises(InitDataValidationError):
            validate_init_data(init_data, bot_token="token", max_age_seconds=300)
