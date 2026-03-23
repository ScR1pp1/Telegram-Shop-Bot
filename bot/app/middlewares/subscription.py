from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.database import SessionFactory
from app.keyboards.inline import check_subscription_kb
from app.models import Channel, Client

logger = logging.getLogger(__name__)


class ChannelCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self.ttl_seconds = ttl_seconds
        self._last_load = 0.0
        self._channels: list[tuple[str, str, str]] = []
        self._lock = asyncio.Lock()

    async def get_channels(self) -> list[tuple[str, str, str]]:
        now = time.time()
        if now - self._last_load < self.ttl_seconds:
            return self._channels
        
        async with self._lock:
            if now - self._last_load < self.ttl_seconds:
                return self._channels
                
            try:
                async with SessionFactory() as s:
                    res = await s.execute(select(Channel))
                    channels = res.scalars().all()

                    for ch in channels:
                        logger.info(f"Channel object: id={ch.id}, channel_id={ch.channel_id}, title={ch.title}")
                        logger.info(f"Has invite_link attr: {hasattr(ch, 'invite_link')}")
                        if hasattr(ch, 'invite_link'):
                            logger.info(f"invite_link value: {ch.invite_link}")
                    
                    channel_list = []
                    for ch in channels:
                        invite_link = getattr(ch, 'invite_link', '')
                        channel_list.append((ch.channel_id, ch.title, invite_link or ""))
                    
                    self._channels = channel_list
                    self._last_load = now
                    logger.info(f"Loaded {len(self._channels)} channels")
            except Exception as e:
                logger.error(f"Error loading channels: {e}")
                
        return self._channels

    async def invalidate(self) -> None:
        """Сброс кэша каналов"""
        async with self._lock:
            self._last_load = 0.0
            self._channels = []
            logger.info("Channel cache invalidated")


channel_cache = ChannelCache(ttl_seconds=300)


class SubscriptionCheckMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        logger.info(f"🔥 Middleware called for {type(event).__name__}")

        client = data.get("client")
        logger.info(f"Client in data: {client}, is_admin: {getattr(client, 'is_admin', None)}")
        
        channels = await channel_cache.get_channels()
        logger.info(f"Channels loaded: {channels}")

        client: Client | None = data.get("client")
        if client and client.is_admin:
            return await handler(event, data)
        
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            ok = await self._is_subscribed(event, data)
            if ok:
                await event.answer("✅ Подписка подтверждена", show_alert=False)
                from aiogram.filters import CommandObject
                from app.handlers.common import start_cmd
                start_command = CommandObject(args="")
                await start_cmd(event.message, client, start_command)
                return None
            await event.answer("❌ Вы ещё не подписаны", show_alert=True)
            await self._ask_to_subscribe(event, data)
            return None

        ok = await self._is_subscribed(event, data)
        if ok:
            return await handler(event, data)

        await self._ask_to_subscribe(event, data)
        return None

    async def _ask_to_subscribe(self, event: TelegramObject, data: dict[str, Any]) -> None:
        bot = data["bot"]
        user = getattr(event, "from_user", None)
        if not user:
            return
        
        channels = await channel_cache.get_channels()
        if not channels:
            return
            
        channels_text = ""
        buttons = []
        
        for ch_id, title, invite_link in channels:
            channels_text += f"🔹 {title}\n"
            
            if invite_link:
                url = invite_link
            elif ch_id.startswith('@'):
                url = f"https://t.me/{ch_id[1:]}"
            else:
                url = None
                
            if url:
                buttons.append([InlineKeyboardButton(
                    text=f"📢 Подписаться на {title}",
                    url=url
                )])
        
        buttons.append([InlineKeyboardButton(
            text="✅ Проверить подписку",
            callback_data="check_subscription"
        )])
        
        await bot.send_message(
            user.id,
            f"🔐 *Для доступа к магазину необходимо подписаться на наши каналы:*\n\n"
            f"{channels_text}\n"
            f"После подписки нажмите кнопку «Проверить»",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="Markdown",
        )

    async def _is_subscribed(self, event: TelegramObject, data: dict[str, Any]) -> bool:
        bot = data["bot"]
        user = getattr(event, "from_user", None)
        if not user:
            return True
            
        channels = await channel_cache.get_channels()
        if not channels:
            return True

        bot_me = await bot.get_me()
        bot_id = bot_me.id

        all_ok = True
        for ch_id, title, _ in channels:
            try:
                try:
                    bot_member = await bot.get_chat_member(chat_id=ch_id, user_id=bot_id)
                except Exception as e:
                    logger.warning(f"Bot not in channel {title} ({ch_id}): {e}")
                    continue

                member = await bot.get_chat_member(chat_id=ch_id, user_id=user.id)
                status = getattr(member, "status", None)
                
                if status in {"left", "kicked"}:
                    logger.info(f"User not subscribed to {title}")
                    all_ok = False
                    
            except Exception as e:
                logger.error(f"Error checking {title}: {e}")
                all_ok = False
                
        return all_ok