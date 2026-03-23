from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from app.database import SessionFactory
from app.models import Client, Order, OrderItem, Product, STATUS_CHOICES

logger = logging.getLogger("bot.orders")
router = Router()


async def get_orders_text_and_kb(client_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Получить текст и клавиатуру для списка заказов"""
    async with SessionFactory() as s:
        res = await s.execute(
            select(Order)
            .where(Order.client_id == client_id)
            .order_by(Order.created_at.desc())
            .limit(10)
        )
        orders = res.scalars().all()
    
    if not orders:
        return "📭 У вас пока нет заказов", InlineKeyboardMarkup(inline_keyboard=[])
    
    text = "📋 *Ваши последние заказы:*\n\n"
    buttons = []
    
    for order in orders:
        if order.status == "cancelled":
            text += f"❌ *Заказ #{order.id}* — отменён\n\n"
        else:
            status_emoji = {
                "pending_payment": "⏳",
                "paid": "✅",
                "processing": "🔄",
                "shipped": "📦",
                "delivered": "🎉"
            }.get(order.status, "📦")
            
            text += f"{status_emoji} *Заказ #{order.id}* от {order.created_at.strftime('%d.%m.%Y')}\n"
            text += f"   Статус: {STATUS_CHOICES.get(order.status, order.status)}\n"
            text += f"   Сумма: {order.total} ₽\n\n"
        
        buttons.append([InlineKeyboardButton(
            text=f"🔍 Посмотреть заказ #{order.id}",
            callback_data=f"order_detail_{order.id}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data="refresh_orders"
    )])
    
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("myorders"))
async def myorders_cmd(message: Message, client: Client):
    """Показать историю заказов пользователя"""
    text, kb = await get_orders_text_and_kb(client.id)
    
    if not kb.inline_keyboard:
        await message.answer(text)
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data.startswith("order_detail_"))
async def order_detail(cb: CallbackQuery, client: Client):
    """Детали конкретного заказа"""
    order_id = int(cb.data.split("_")[2])
    
    async with SessionFactory() as s:
        res = await s.execute(
            select(Order).where(Order.id == order_id, Order.client_id == client.id)
        )
        order = res.scalar_one_or_none()
        
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        
        items_res = await s.execute(
            select(Product.name, OrderItem.quantity, OrderItem.price)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order_id)
        )
        items = items_res.all()
    
    items_text = ""
    for name, qty, price in items:
        items_text += f"• {name} × {qty} = {price * qty} ₽\n"
    
    text = (
        f"📦 *Заказ #{order.id}*\n\n"
        f"📅 Дата: {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📊 Статус: {STATUS_CHOICES.get(order.status, order.status)}\n"
        f"👤 Получатель: {order.full_name}\n"
        f"📍 Адрес: {order.address}\n"
        f"📞 Телефон: {order.phone}\n\n"
        f"🛒 *Товары:*\n{items_text}\n"
        f"💰 *Итого:* {order.total} ₽"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Ссылка на заказ", url=f"https://t.me/task_shop_bot?start=order_{order_id}")],
        [InlineKeyboardButton(text="◀️ Назад к заказам", callback_data="back_to_orders")]
    ])
    
    await cb.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await cb.answer()


@router.callback_query(F.data == "back_to_orders")
async def back_to_orders(cb: CallbackQuery, client: Client):
    """Вернуться к списку заказов"""
    text, kb = await get_orders_text_and_kb(client.id)
    
    try:
        await cb.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await cb.answer("✅ Список заказов")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer("✅ Данные актуальны")
        else:
            raise e
    
    await cb.answer()


@router.callback_query(F.data == "refresh_orders")
async def refresh_orders(cb: CallbackQuery, client: Client):
    """Обновить список заказов"""
    text, kb = await get_orders_text_and_kb(client.id)
    
    try:
        await cb.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        await cb.answer("🔄 Список обновлён")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await cb.answer("✅ Заказы не изменились")
        else:
            raise e
    
    await cb.answer()