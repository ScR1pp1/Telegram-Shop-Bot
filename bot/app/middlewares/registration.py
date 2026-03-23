from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.database import SessionFactory
from app.models import Client


class RegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        async with SessionFactory() as s:
            res = await s.execute(select(Client).where(Client.telegram_id == from_user.id))
            client = res.scalar_one_or_none()
            
            if client is None:
                try:
                    client = Client(
                        telegram_id=from_user.id,
                        username=from_user.username,
                        first_name=from_user.first_name or "",
                        last_name=from_user.last_name or "",
                        is_admin=False,
                        is_active=True,
                    )
                    s.add(client)
                    await s.commit()
                    await s.refresh(client)
                except IntegrityError:
                    await s.rollback()
                    res = await s.execute(select(Client).where(Client.telegram_id == from_user.id))
                    client = res.scalar_one_or_none()
            else:
                await s.execute(
                    update(Client)
                    .where(Client.id == client.id)
                    .values(
                        username=from_user.username,
                        first_name=from_user.first_name or "",
                        last_name=from_user.last_name or "",
                    )
                )
                await s.commit()
                await s.refresh(client)

        data["client"] = client
        return await handler(event, data)