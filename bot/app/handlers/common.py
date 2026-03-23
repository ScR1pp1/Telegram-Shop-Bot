from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message, InputMediaPhoto
from sqlalchemy import update
from decimal import Decimal

from app.database import SessionFactory
from app.keyboards.reply import request_contact_kb
from app.models import STATUS_CHOICES, Client, Order, OrderItem, Product
from app.utils.catalog import (
    categories_kb,
    get_root_categories,
    get_product,
    get_product_images,
    product_card_kb,
    _image_to_tg_media,
)
from app.utils.cart import get_cart_lines

logger = logging.getLogger("bot.common")
router = Router()


@router.message(Command("start"))
async def start_cmd(message: Message, client: Client, command: CommandObject):
    """Обработчик команды /start"""
    if not client.phone_number:
        welcome_text = (
            "👋 *Добро пожаловать в Telegram Shop Bot!*\n\n"
            "🔐 Для продолжения работы необходимо поделиться номером телефона.\n"
            "Это займёт всего секунду и позволит нам:\n"
            "✅ Сохранять вашу корзину\n"
            "✅ Оформлять заказы быстрее\n"
            "✅ Уведомлять о статусе заказов\n\n"
            "📱 Нажмите кнопку ниже, чтобы поделиться контактом."
        )
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=request_contact_kb())
        return

    name = message.from_user.first_name or "пользователь"

    if command.args and command.args.startswith("product_"):
        try:
            product_id = int(command.args.split("_", 1)[1])
        except Exception:
            product_id = None
        if product_id:
            p = await get_product(product_id)
            if p:
                imgs = await get_product_images(p.id)
                if imgs:
                    first_url = _image_to_tg_media(imgs[0].image)
                    await message.answer_photo(
                        photo=first_url,
                        caption=(
                            f"✨ *{p.name}*\n\n"
                            f"📝 {p.description}\n\n"
                            f"💰 *Цена:* {p.price} ₽"
                        ),
                        reply_markup=product_card_kb(p.id),
                        parse_mode="Markdown"
                    )
                    if len(imgs) > 1:
                        media_group = []
                        for img in imgs[1:]:
                            url = _image_to_tg_media(img.image)
                            if url:
                                media_group.append(InputMediaPhoto(media=url))
                        if media_group:
                            await message.answer_media_group(media_group)
                else:
                    product_text = (
                        f"✨ *{p.name}*\n\n"
                        f"📝 {p.description}\n\n"
                        f"💰 *Цена:* {p.price} ₽"
                    )
                    await message.answer(
                        product_text,
                        reply_markup=product_card_kb(p.id),
                        parse_mode="Markdown",
                    )
                return

    if command.args and command.args.startswith("order_"):
        try:
            order_id = int(command.args.split("_", 1)[1])
        except Exception:
            order_id = None
        if order_id:
            from app.models import Order, OrderItem, Product
            from sqlalchemy import select
            from decimal import Decimal
            
            async with SessionFactory() as s:
                res = await s.execute(
                    select(Order).where(Order.id == order_id, Order.client_id == client.id)
                )
                order = res.scalar_one_or_none()
                
                if order:
                    items_res = await s.execute(
                        select(Product.name, OrderItem.quantity, OrderItem.price)
                        .join(OrderItem, OrderItem.product_id == Product.id)
                        .where(OrderItem.order_id == order_id)
                    )
                    items = items_res.all()
                    
                    items_text = ""
                    for name, qty, price in items:
                        items_text += f"• {name} × {qty} = {price * qty} ₽\n"
                    
                    order_text = (
                        f"📦 *Заказ #{order.id}*\n\n"
                        f"📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"📊 Статус: {STATUS_CHOICES.get(order.status, order.status)}\n"
                        f"👤 Получатель: {order.full_name}\n"
                        f"📍 Адрес: {order.address}\n"
                        f"📞 Телефон: {order.phone}\n\n"
                        f"🛒 *Товары:*\n{items_text}\n"
                        f"💰 *Итого:* {order.total} ₽"
                    )
                    
                    await message.answer(order_text, parse_mode="Markdown")
                    return
                else:
                    await message.answer("❌ Заказ не найден или не принадлежит вам")
                    return

    lines, total_items = await get_cart_lines(client.id, 0)
    if lines:
        total_sum = sum(price * qty for _, qty, _, _, price in lines)
        cart_text = f"\n\n🛒 *В корзине:* {len(lines)} товаров на {total_sum} ₽"
    else:
        cart_text = ""

    welcome_text = (
        f"👋 *С возвращением, {name}!*{cart_text}\n\n"
        "🛍 *Telegram Shop Bot* — ваш удобный помощник для покупок.\n\n"
        "📌 *Основные возможности:*\n"
        "▫️ Просмотр каталога с удобной навигацией\n"
        "▫️ Добавление товаров в корзину\n"
        "▫️ Оформление заказа в несколько шагов\n"
        "▫️ Отслеживание статуса заказа\n\n"
        "⚡️ *Команды:*\n"
        "/catalog — открыть каталог\n"
        "/cart — просмотреть корзину\n"
        "/myorders — история заказов\n"
        "/help — подробная справка\n\n"
        "🎁 *Удачных покупок!*"
    )

    await message.answer(welcome_text, parse_mode="Markdown")


@router.message(F.contact)
async def contact_msg(message: Message, client: Client):
    """Обработчик получения контакта"""
    if not message.contact or not message.contact.phone_number:
        await message.answer("❌ Контакт не распознан. Попробуйте ещё раз.")
        return
        
    if message.from_user and message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer("❌ Пожалуйста, отправьте свой собственный контакт.")
        return

    async with SessionFactory() as s:
        await s.execute(
            update(Client)
            .where(Client.id == client.id)
            .values(phone_number=message.contact.phone_number)
        )
        await s.commit()

    client.phone_number = message.contact.phone_number
    
    success_text = (
        "✅ *Телефон успешно сохранён!*\n\n"
        "Теперь вам доступны все функции магазина:\n"
        "🛒 Просмотр каталога\n"
        "📦 Оформление заказов\n"
        "🔔 Уведомления о статусе\n\n"
        "⚡️ Нажмите /catalog, чтобы начать покупки!"
    )
    await message.answer(success_text, parse_mode="Markdown", reply_markup=None)
    
    empty_command = CommandObject(args="")
    await start_cmd(message, client, empty_command)


@router.message(Command("help"))
async def help_cmd(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "<b>📚 Справка по командам</b>\n\n"
        "/start — главное меню и регистрация\n"
        "/catalog — открыть каталог товаров\n"
        "/cart — просмотреть корзину\n"
        "/help — показать эту справку\n\n"
        "<b>🛒 Как сделать заказ:</b>\n"
        "1️⃣ Откройте каталог (/catalog)\n"
        "2️⃣ Выберите категорию и товар\n"
        "3️⃣ Нажмите «В корзину»\n"
        "4️⃣ Перейдите в корзину (/cart)\n"
        "5️⃣ Нажмите «Оформить заказ»\n"
        "6️⃣ Заполните данные и подтвердите\n\n"
        "<b>🔍 Поиск по FAQ:</b>\n"
        "В любом чате наберите @task_shop_bot ваш вопрос\n\n"
        "<b>📞 Поддержка:</b>\n"
        "По всем вопросам обращайтесь к @forever_younnng"
    )
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("catalog"))
async def catalog_cmd(message: Message):
    """Обработчик команды /catalog"""
    cats = await get_root_categories()
    if not cats:
        await message.answer("📭 *Каталог пуст*\n\nТовары появятся позже. Загляните позже!")
        return
    
    catalog_text = "📋 *Каталог товаров*\n\nВыберите категорию:"
    await message.answer(catalog_text, reply_markup=categories_kb(cats))


@router.callback_query()
async def unknown_callback(cb: CallbackQuery):
    """Обработчик неизвестных callback'ов"""
    logger.warning(f"Unknown callback from user {cb.from_user.id}: {cb.data}")
    try:
        await cb.answer("⏳ Кнопка устарела, попробуйте ещё раз", show_alert=False)
    except Exception:
        pass