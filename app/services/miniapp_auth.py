from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class MiniAppUser:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None


def _build_data_check_string(init_data: str) -> tuple[str, str | None]:
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)

    pairs = [f"{key}={value}" for key, value in sorted(parsed.items())]
    return "\n".join(pairs), received_hash


def verify_telegram_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> bool:
    if not init_data or not bot_token:
        return False

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    auth_date_raw = parsed.get("auth_date")

    if not auth_date_raw or not auth_date_raw.isdigit():
        return False

    auth_date = int(auth_date_raw)
    if time.time() - auth_date > max_age_seconds:
        return False

    data_check_string, received_hash = _build_data_check_string(init_data)
    if not received_hash:
        return False

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    calculated_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(calculated_hash, received_hash)


def extract_user_from_init_data(init_data: str) -> MiniAppUser | None:
    import json

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    user_raw = parsed.get("user")

    if not user_raw:
        return None

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None

    telegram_id = user.get("id")
    if not isinstance(telegram_id, int):
        return None

    return MiniAppUser(
        telegram_id=telegram_id,
        username=user.get("username"),
        first_name=user.get("first_name"),
        last_name=user.get("last_name"),
    )
