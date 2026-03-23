from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


logger = logging.getLogger("bot.updates")


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "telegram_id": getattr(from_user, "id", None),
            "event_type": event.__class__.__name__,
        }
        try:
            logger.info(json.dumps(payload, ensure_ascii=False))
        except Exception:
            logger.info("update: %s", payload)
        return await handler(event, data)

