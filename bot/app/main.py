from __future__ import annotations

import asyncio
import logging
import os
import contextlib
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.config import settings
from app.handlers.catalog import router as catalog_router
from app.handlers.cart import router as cart_router
from app.handlers.common import router as common_router
from app.handlers.order import router as order_router
from app.handlers.admin_chat import router as admin_chat_router
from app.handlers.faq import router as faq_router
from app.handlers.wishlist import router as wishlist_router
from app.middlewares.logging import LoggingMiddleware
from app.middlewares.registration import RegistrationMiddleware
from app.middlewares.subscription import SubscriptionCheckMiddleware
from app.notifier import listen_order_status_changed, listen_channel_changed
from app.mailing_worker import mailing_loop
from app.handlers.orders_history import router as orders_history_router


def _setup_logging() -> None:
    os.makedirs(settings.LOG_DIR, exist_ok=True)
    log_path = os.path.join(settings.LOG_DIR, settings.LOG_FILE)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)


async def _set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="catalog", description="Каталог товаров"),
            BotCommand(command="cart", description="Корзина"),
            BotCommand(command="wishlist", description="Избранное"),
            BotCommand(command="myorders", description="Мои заказы"),
            BotCommand(command="help", description="Справка"),
        ]
    )


async def main() -> None:
    _setup_logging()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    dp.message.middleware(RegistrationMiddleware())
    dp.callback_query.middleware(RegistrationMiddleware())
    dp.inline_query.middleware(RegistrationMiddleware())

    dp.message.middleware(SubscriptionCheckMiddleware())
    dp.callback_query.middleware(SubscriptionCheckMiddleware())

    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    dp.inline_query.middleware(LoggingMiddleware())

    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(order_router)
    dp.include_router(admin_chat_router)
    dp.include_router(faq_router)
    dp.include_router(orders_history_router)
    dp.include_router(wishlist_router)
    dp.include_router(common_router)

    stop_event = asyncio.Event()
    notifier_task = asyncio.create_task(listen_order_status_changed(stop_event, bot=bot))
    channel_listener_task = asyncio.create_task(listen_channel_changed(stop_event))
    mailing_task = asyncio.create_task(mailing_loop(stop_event, bot))

    try:
        await _set_commands(bot)
        await dp.start_polling(bot)
    finally:
        stop_event.set()
        notifier_task.cancel()
        channel_listener_task.cancel()
        mailing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await notifier_task
        with contextlib.suppress(asyncio.CancelledError):
            await channel_listener_task
        with contextlib.suppress(asyncio.CancelledError):
            await mailing_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())