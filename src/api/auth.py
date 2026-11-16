import hashlib
import hmac
import json
import re
import time
import urllib.parse
from fastapi import Header, HTTPException
from src.config import settings


def verify_telegram_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData using HMAC-SHA256."""
    if not init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    if len(init_data) > 8192:
        raise HTTPException(status_code=401, detail="initData is too large")

    try:
        parsed_data = urllib.parse.parse_qsl(
            init_data,
            keep_blank_values=True,
            strict_parsing=True,
        )
        data_map = dict(parsed_data)
        if len(data_map) != len(parsed_data):
            raise HTTPException(status_code=401, detail="Duplicate initData fields")
        received_hash = data_map.pop("hash", None)
        if not received_hash or re.fullmatch(r"[a-fA-F0-9]{64}", received_hash) is None:
            raise HTTPException(status_code=401, detail="Invalid initData format")

        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(data_map.items())
        )

        secret_key = hmac.new(
            b"WebAppData",
            settings.TELEGRAM_BOT_TOKEN.encode("utf-8"),
            hashlib.sha256
        ).digest()

        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            raise HTTPException(status_code=401, detail="Invalid signature")

        auth_date = int(data_map["auth_date"])
        age_seconds = int(time.time()) - auth_date
        if age_seconds < -30 or age_seconds > settings.TELEGRAM_INIT_DATA_MAX_AGE_SECONDS:
            raise HTTPException(status_code=401, detail="Expired initData")

        user_json = data_map.get("user")
        if not user_json:
            raise HTTPException(status_code=401, detail="initData has no user")
        user = json.loads(user_json)
        if not isinstance(user, dict) or type(user.get("id")) is not int or user["id"] <= 0:
            raise HTTPException(status_code=401, detail="Invalid Telegram user")
        return user
    except HTTPException:
        raise
    except (KeyError, ValueError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=401, detail="Malformed initData") from error


async def require_telegram_user(
    x_telegram_init_data: str | None = Header(default=None),
) -> dict:
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Missing initData")
    return verify_telegram_init_data(x_telegram_init_data)
