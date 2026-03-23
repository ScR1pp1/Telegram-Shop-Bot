from __future__ import annotations

import asyncio
import logging

import aiohttp
from sqlalchemy import select, update

from app.config import settings
from app.database import SessionFactory
from app.models import Client, Mailing

logger = logging.getLogger("bot.mailings")


async def mailing_loop(stop_event: asyncio.Event, bot) -> None:
    while not stop_event.is_set():
        try:
            await _tick(bot)
        except Exception as e:
            logger.error(f"Mailing worker error: {e}")
        await asyncio.sleep(10)


async def _tick(bot) -> None:
    try:
        async with SessionFactory() as s:
            res = await s.execute(
                select(Mailing).where(Mailing.status == "ready").order_by(Mailing.id.asc()).limit(5)
            )
            mailings = list(res.scalars().all())
    except Exception as e:
        logger.error(f"Failed to fetch mailings: {e}")
        return

    for m in mailings:
        await _send_one(bot, m.id)


async def _check_image_accessible(url: str) -> bool:
    """Проверяет доступность изображения по URL (HEAD-запрос)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
    except Exception as e:
        logger.warning(f"Image check failed for {url}: {e}")
        return False


async def _send_one(bot, mailing_id: int) -> None:
    try:
        async with SessionFactory() as s:
            res = await s.execute(select(Mailing).where(Mailing.id == mailing_id))
            m = res.scalar_one_or_none()
            if not m or m.status != "ready":
                return
            
            await s.execute(
                update(Mailing)
                .where(Mailing.id == mailing_id)
                .values(status="sending", stats_sent=0, stats_failed=0)
            )
            await s.commit()
    except Exception as e:
        logger.error(f"Failed to start mailing {mailing_id}: {e}")
        return

    sent = 0
    failed = 0
    image_url = None
    send_image = False
    
    if m.image:
        base = settings.DJANGO_BASE_URL.rstrip("/")
        image_url = f"{base}/media/{m.image.lstrip('/')}"
        send_image = await _check_image_accessible(image_url)
        if not send_image:
            logger.warning(f"Image {image_url} not accessible, will send without photo")

    try:
        async with SessionFactory() as s:
            res = await s.execute(select(Client.telegram_id).where(Client.is_active.is_(True)))
            telegram_ids = [r[0] for r in res.all()]
    except Exception as e:
        logger.error(f"Failed to get user list for mailing {mailing_id}: {e}")
        return

    for tid in telegram_ids:
        try:
            if send_image and image_url:
                await bot.send_photo(tid, photo=image_url, caption=f"{m.subject}\n\n{m.text}")
            else:
                await bot.send_message(tid, f"{m.subject}\n\n{m.text}")
            sent += 1
        except Exception as e:
            failed += 1
            logger.error(f"Failed to send mailing {mailing_id} to {tid}: {e}")
        await asyncio.sleep(0.05)

    try:
        async with SessionFactory() as s:
            await s.execute(
                update(Mailing)
                .where(Mailing.id == mailing_id)
                .values(status="sent", stats_sent=sent, stats_failed=failed)
            )
            await s.commit()
        logger.info(f"Mailing {mailing_id} completed: {sent} sent, {failed} failed")
    except Exception as e:
        logger.error(f"Failed to update mailing stats {mailing_id}: {e}")