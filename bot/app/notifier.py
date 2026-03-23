from __future__ import annotations

import asyncio
import json
import logging

import asyncpg
from sqlalchemy import select

from .config import settings
from .database import SessionFactory
from .models import Client, Order

from app.middlewares.subscription import channel_cache

logger = logging.getLogger("bot.notifier")

_notifier_lock = asyncio.Lock()


async def listen_order_status_changed(stop_event: asyncio.Event, bot=None) -> None:
    """Слушатель изменений статуса заказа."""
    conn: asyncpg.Connection | None = None
    while not stop_event.is_set():
        try:
            conn = await asyncpg.connect(settings.asyncpg_dsn)
            await conn.add_listener("order_status_changed", lambda *args: _on_notify(bot, *args))
            logger.info("LISTEN order_status_changed started")
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        except Exception:
            logger.exception("Notifier error, reconnecting in 2s")
            await asyncio.sleep(2)
        finally:
            try:
                if conn:
                    await conn.close()
            except Exception:
                pass


async def listen_channel_changed(stop_event: asyncio.Event) -> None:
    """Слушатель изменений каналов (для инвалидации кэша)."""
    conn: asyncpg.Connection | None = None
    while not stop_event.is_set():
        try:
            conn = await asyncpg.connect(settings.asyncpg_dsn)
            await conn.add_listener("channel_changed", lambda *args: _on_channel_changed())
            logger.info("LISTEN channel_changed started")
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        except Exception:
            logger.exception("Channel listener error, reconnecting in 2s")
            await asyncio.sleep(2)
        finally:
            try:
                if conn:
                    await conn.close()
            except Exception:
                pass


def _on_notify(bot, connection: asyncpg.Connection, pid: int, channel: str, payload: str) -> None:
    try:
        data = json.loads(payload)
    except Exception:
        data = {"raw": payload}
    logger.info("NOTIFY %s: %s", channel, data)

    if bot is None:
        return
    try:
        order_id = int(data.get("order_id"))
        status = str(data.get("status"))
    except Exception:
        return
    asyncio.create_task(_send_status_with_lock(bot, order_id, status))


def _on_channel_changed() -> None:
    """Вызывается при получении NOTIFY channel_changed."""
    logger.info("Channel changed, invalidating cache")
    asyncio.create_task(channel_cache.invalidate())


async def _send_status_with_lock(bot, order_id: int, status: str) -> None:
    async with _notifier_lock:
        await _send_status(bot, order_id, status)


async def _send_status(bot, order_id: int, status: str) -> None:
    async with SessionFactory() as s:
        order = (await s.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
        if not order:
            return
        client = (await s.execute(select(Client).where(Client.id == order.client_id))).scalar_one_or_none()
        if not client:
            return
        telegram_id = client.telegram_id

    await bot.send_message(telegram_id, f"Статус заказа #{order_id} изменён: {status}")