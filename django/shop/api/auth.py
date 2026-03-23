from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl

from django.conf import settings
from rest_framework import authentication, exceptions

from shop.models import Client


@dataclass(frozen=True)
class TelegramInitData:
    raw: str
    values: dict[str, str]

    @property
    def telegram_id(self) -> int | None:
        u = self.values.get("user")
        if not u:
            return None
        try:
            import json

            data = json.loads(u)
            return int(data.get("id")) if data.get("id") is not None else None
        except Exception:
            return None


def _validate_init_data(init_data_raw: str, bot_token: str) -> TelegramInitData:
    pairs = dict(parse_qsl(init_data_raw, keep_blank_values=True))
    provided_hash = pairs.get("hash")
    if not provided_hash:
        raise exceptions.AuthenticationFailed("initData missing hash")

    data_check_arr: list[str] = []
    for k, v in sorted(pairs.items()):
        if k == "hash":
            continue
        data_check_arr.append(f"{k}={v}")
    data_check_string = "\n".join(data_check_arr).encode("utf-8")

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, provided_hash):
        raise exceptions.AuthenticationFailed("Bad initData signature")

    return TelegramInitData(raw=init_data_raw, values=pairs)


def _extract_user_fields(init_data: TelegramInitData) -> dict[str, Any]:
    import json

    user_json = init_data.values.get("user")
    if not user_json:
        return {}
    data = json.loads(user_json)
    return {
        "telegram_id": int(data["id"]),
        "username": data.get("username"),
        "first_name": data.get("first_name", "") or "",
        "last_name": data.get("last_name", "") or "",
    }


class TelegramInitDataAuthentication(authentication.BaseAuthentication):
    """
    Expects: Authorization: tma <initData>
    """

    keyword = "tma"

    def authenticate(self, request):
        header = request.headers.get("Authorization")
        if not header:
            return None
        if not header.lower().startswith(self.keyword):
            return None
        parts = header.split(" ", 1)
        if len(parts) != 2:
            raise exceptions.AuthenticationFailed("Invalid Authorization header")
        init_data_raw = parts[1].strip()
        if not init_data_raw:
            raise exceptions.AuthenticationFailed("Empty initData")

        bot_token = settings.BOT_TOKEN
        if not bot_token:
            raise exceptions.AuthenticationFailed("Server misconfigured: BOT_TOKEN missing")

        init_data = _validate_init_data(init_data_raw, bot_token)
        fields = _extract_user_fields(init_data)
        if not fields:
            raise exceptions.AuthenticationFailed("initData missing user")

        client, _ = Client.objects.get_or_create(
            telegram_id=fields["telegram_id"],
            defaults={
                "username": fields.get("username"),
                "first_name": fields.get("first_name", ""),
                "last_name": fields.get("last_name", ""),
            },
        )
        return (client, init_data.raw)

    def authenticate_header(self, request) -> str:
        return self.keyword