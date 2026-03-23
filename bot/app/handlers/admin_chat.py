from __future__ import annotations
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select, update

from app.filters.is_admin import IsAdmin
from app.database import SessionFactory
from app.models import Client, Order, OrderItem, Product, Setting


router = Router()


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Принять", callback_data=f"ast:{order_id}:processing"),
                InlineKeyboardButton(text="Отгружен", callback_data=f"ast:{order_id}:shipped"),
            ],
            [InlineKeyboardButton(text="Отменён", callback_data=f"ast:{order_id}:cancelled")],
        ]
    )


async def get_admin_chat_id() -> int | None:
    async with SessionFactory() as s:
        res = await s.execute(select(Setting.value).where(Setting.key == "admin_chat_id"))
        row = res.first()
        if not row:
            return None
        try:
            return int(row[0])
        except Exception:
            return None


async def send_order_to_admin(bot, order_id: int) -> None:
    chat_id = await get_admin_chat_id()
    if not chat_id:
        return
    async with SessionFactory() as s:
        res = await s.execute(select(Order).where(Order.id == order_id))
        order = res.scalar_one_or_none()
        if not order:
            return
        client = (await s.execute(select(Client).where(Client.id == order.client_id))).scalar_one_or_none()
        items = await s.execute(
            select(Product.name, OrderItem.quantity, OrderItem.price)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order_id)
        )
        lines = [f"- {n} × {q} = {p * q}" for n, q, p in items.all()]
        text = (
            f"Заказ #{order.id}\n"
            f"Статус: {order.status}\n"
            f"Клиент: {client.telegram_id if client else order.client_id}\n"
            f"Сумма: {order.total}\n"
            + "\n".join(lines)
        )
    await bot.send_message(chat_id, text, reply_markup=admin_order_kb(order_id))


@router.message(Command("active_orders"), IsAdmin())
async def active_orders(message: Message):
    async with SessionFactory() as s:
        res = await s.execute(
            select(Order.id, Order.status, Order.total)
            .where(Order.status.not_in(["delivered", "cancelled"]))
            .order_by(Order.id.desc())
            .limit(30)
        )
        rows = res.all()
    if not rows:
        await message.answer("Нет активных заказов / No active orders.")
        return
    text = "Активные заказы / Active orders:\n\n" + "\n".join([f"#{i} — {st} — {tot}" for i, st, tot in rows])
    await message.answer(text)


@router.callback_query(F.data.startswith("ast:"))
async def admin_set_status(cb: CallbackQuery):
    if cb.from_user is None:
        await cb.answer()
        return

    async with SessionFactory() as s:
        res = await s.execute(select(Client.is_admin).where(Client.telegram_id == cb.from_user.id))
        row = res.first()
        if not row or not row[0]:
            await cb.answer("Forbidden", show_alert=True)
            return

    try:
        _, order_id_s, status = cb.data.split(":", 2)
        order_id = int(order_id_s)
    except Exception:
        await cb.answer("Bad data", show_alert=True)
        return

    async with SessionFactory() as s:
        await s.execute(update(Order).where(Order.id == order_id).values(status=status))
        await s.commit()

    if cb.message:
        await cb.message.edit_reply_markup(reply_markup=None)
        await cb.message.answer(f"Статус заказа #{order_id} → {status}")
    await cb.answer("OK")


@router.callback_query(F.data.startswith("contact_customer_"))
async def contact_customer(cb: CallbackQuery):
    """Кнопка для связи с клиентом"""
    try:
        order_id = int(cb.data.split("_")[2])
    except Exception:
        await cb.answer("Ошибка", show_alert=True)
        return
    
    async with SessionFactory() as s:
        res = await s.execute(
            select(Order).where(Order.id == order_id)
        )
        order = res.scalar_one_or_none()
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        
        client_res = await s.execute(
            select(Client).where(Client.id == order.client_id)
        )
        client = client_res.scalar_one_or_none()
    
    if client and client.telegram_id:
        await cb.message.answer(
            f"📞 Связь с клиентом по заказу #{order_id}:\n"
            f"Telegram ID: {client.telegram_id}\n"
            f"Username: @{client.username if client.username else 'не указан'}\n"
            f"Телефон: {client.phone_number}"
        )
    else:
        await cb.message.answer("❌ Контактные данные не найдены")
    
    await cb.answer()


@router.message(Command("stats"))
async def chat_stats(message: Message):
    """Статистика по заказам в админ-чате"""
    async with SessionFactory() as s:
        total_orders = await s.execute(select(func.count(Order.id)))
        total = total_orders.scalar()
        
        today = datetime.now().date()
        today_orders = await s.execute(
            select(func.count(Order.id)).where(func.date(Order.created_at) == today)
        )
        today_count = today_orders.scalar()
        
        status_counts = {}
        for status, _ in Order.STATUS_CHOICES:
            count = await s.execute(
                select(func.count(Order.id)).where(Order.status == status)
            )
            status_counts[status] = count.scalar()
    
    text = (
        f"📊 *Статистика заказов*\n\n"
        f"Всего заказов: {total}\n"
        f"За сегодня: {today_count}\n\n"
        f"По статусам:\n"
        f"⏳ Ожидают оплаты: {status_counts.get('pending_payment', 0)}\n"
        f"✅ Оплачены: {status_counts.get('paid', 0)}\n"
        f"🔄 В обработке: {status_counts.get('processing', 0)}\n"
        f"📦 Отгружены: {status_counts.get('shipped', 0)}\n"
        f"🎉 Доставлены: {status_counts.get('delivered', 0)}\n"
        f"❌ Отменены: {status_counts.get('cancelled', 0)}"
    )
    
    await message.answer(text, parse_mode="Markdown")