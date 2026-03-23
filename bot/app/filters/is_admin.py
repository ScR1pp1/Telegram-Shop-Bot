from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from sqlalchemy import select

from app.database import SessionFactory
from app.models import Client


class IsAdmin(BaseFilter):
    async def __call__(self, obj: TelegramObject, **data) -> bool:
        client: Client | None = data.get("client")
        if client is not None:
            return bool(getattr(client, "is_admin", False))

        telegram_id = None
        if hasattr(obj, "from_user") and getattr(obj, "from_user"):
            telegram_id = obj.from_user.id
        if telegram_id is None:
            return False

        async with SessionFactory() as s:
            res = await s.execute(select(Client.is_admin).where(Client.telegram_id == telegram_id))
            row = res.first()
            return bool(row[0]) if row else False

