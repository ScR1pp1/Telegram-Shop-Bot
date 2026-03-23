from __future__ import annotations

import logging
import re
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import delete, insert, select, update

from app.callbacks import CartCheckoutCb
from app.config import settings
from app.database import SessionFactory
from app.models import CartItem, Client, Order, OrderItem, Product, Setting
from app.states.order import OrderFSM
from app.utils.cart import get_cart_lines, render_cart

logger = logging.getLogger("bot.order")
router = Router()



def validate_name_part(name_part: str, field_name: str) -> tuple[bool, str]:
    """
    Валидация отдельной части ФИО:
    - Только русские буквы, дефис
    - Начинается с заглавной
    - Длина от 2 до 50 символов
    """
    name_part = name_part.strip()
    
    if not name_part:
        return False, f"{field_name} не может быть пустым"
    
    if len(name_part) < 2:
        return False, f"{field_name} должно содержать минимум 2 символа"
    
    if len(name_part) > 50:
        return False, f"{field_name} слишком длинное (максимум 50 символов)"
    
    if not re.match(r'^[А-ЯЁ][а-яё]*(-[А-ЯЁ][а-яё]*)?$', name_part):
        return False, f"{field_name} должно начинаться с заглавной буквы и содержать только русские буквы (дефис допустим для двойных)"
    
    return True, ""


def validate_city(city: str) -> tuple[bool, str]:
    """Валидация названия города"""
    city = city.strip()
    
    if not city:
        return False, "Город не может быть пустым"
    
    if len(city) < 2:
        return False, "Название города слишком короткое"
    
    if len(city) > 50:
        return False, "Название города слишком длинное"
    
    if not re.match(r'^[А-ЯЁ][а-яё\s\-]+$', city):
        return False, "Город должен начинаться с заглавной буквы и содержать только русские буквы"
    
    return True, ""


def validate_street(street: str) -> tuple[bool, str]:
    """Валидация названия улицы"""
    street = street.strip()
    
    if not street:
        return False, "Улица не может быть пустой"
    
    if len(street) < 3:
        return False, "Название улицы слишком короткое"
    
    if len(street) > 100:
        return False, "Название улицы слишком длинное"
    
    if not re.match(r'^[А-ЯЁ][а-яё\s\-\.]+$', street):
        return False, "Улица должна начинаться с заглавной буквы"
    
    return True, ""


def validate_house_number(house: str) -> tuple[bool, str]:
    """Валидация номера дома"""
    house = house.strip()
    
    if not house:
        return False, "Номер дома не может быть пустым"
    
    if not re.match(r'^\d+[а-яА-Яa-zA-Z]?(/\d+)?$', house):
        return False, "Номер дома должен содержать цифры (возможно с буквой или дробью)"
    
    return True, ""


def validate_apartment(apt: str) -> tuple[bool, str]:
    """Валидация номера квартиры (опционально)"""
    apt = apt.strip()
    
    if not apt:
        return True, ""
    
    if not re.match(r'^\d+$', apt):
        return False, "Номер квартиры должен содержать только цифры"
    
    if len(apt) > 10:
        return False, "Номер квартиры слишком длинный"
    
    return True, ""


def validate_floor(floor: str) -> tuple[bool, str]:
    """Валидация этажа (опционально)"""
    floor = floor.strip()
    
    if not floor:
        return True, ""
    
    if not re.match(r'^\d+$', floor):
        return False, "Этаж должен содержать только цифры"
    
    if int(floor) > 100:
        return False, "Этаж не может быть больше 100"
    
    return True, ""



def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="order_confirm")],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data="order_edit")],
            [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="order_edit_cancel")]
        ]
    )


def pay_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Я оплатил / I paid", callback_data=f"pay:{order_id}")]]
    )



async def _get_admin_chat_id() -> int | None:
    async with SessionFactory() as s:
        res = await s.execute(select(Setting.value).where(Setting.key == "admin_chat_id"))
        row = res.first()
        if not row:
            return None
        try:
            return int(row[0])
        except Exception:
            return None


async def _create_order(client: Client, full_name: str, address: str) -> int | None:
    async with SessionFactory() as s:
        res = await s.execute(
            select(CartItem.product_id, CartItem.quantity, Product.price, Product.name)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.client_id == client.id)
        )
        items = res.all()
        if not items:
            return None

        total = Decimal("0.00")
        for product_id, qty, price, name in items:
            total += price * qty

        order_res = await s.execute(
            insert(Order)
            .values(
                client_id=client.id,
                full_name=full_name,
                address=address,
                phone=client.phone_number or "",
                total=total,
                status="pending_payment",
            )
            .returning(Order.id)
        )
        order_id = int(order_res.scalar_one())

        await s.execute(
            insert(OrderItem),
            [
                {"order_id": order_id, "product_id": pid, "quantity": qty, "price": price}
                for pid, qty, price, name in items
            ],
        )
        await s.execute(delete(CartItem).where(CartItem.client_id == client.id))
        await s.commit()
        
        logger.info(f"Order {order_id} created for client {client.id}")
        return order_id


async def _notify_admin_new_order(bot, order_id: int, client: Client) -> None:
    admin_chat_id = await _get_admin_chat_id()
    if not admin_chat_id:
        return
    async with SessionFactory() as s:
        res = await s.execute(select(Order).where(Order.id == order_id))
        order = res.scalar_one_or_none()
        if not order:
            return
        items = await s.execute(
            select(Product.name, OrderItem.quantity, OrderItem.price)
            .join(OrderItem, OrderItem.product_id == Product.id)
            .where(OrderItem.order_id == order_id)
        )
        lines = [f"- {n} × {q} = {p * q}" for n, q, p in items.all()]
        text = (
            f"🆕 Новый заказ #{order.id}\n"
            f"Клиент: {client.telegram_id} @{client.username or '-'}\n"
            f"Сумма: {order.total}\n"
            + "\n".join(lines)
        )
    await bot.send_message(admin_chat_id, text)



@router.callback_query(CartCheckoutCb.filter())
async def checkout_from_cart(cb: CallbackQuery, state: FSMContext):
    logger.info(f"User {cb.from_user.id} started checkout from cart")
    await state.set_state(OrderFSM.last_name)
    await cb.message.answer("👤 Введите фамилию / Enter last name (например: Иванов):")
    await cb.answer()


@router.message(Command("checkout"))
async def checkout_cmd(message: Message, state: FSMContext, client: Client):
    lines, total = await get_cart_lines(client.id, 0)
    if not lines:
        logger.info(f"User {client.telegram_id} tried checkout with empty cart")
        await message.answer("❌ Корзина пуста / Cart is empty.")
        return
    
    logger.info(f"User {client.telegram_id} started checkout")
    await state.set_state(OrderFSM.last_name)
    await message.answer("👤 Введите фамилию / Enter last name (например: Иванов):")


@router.message(OrderFSM.last_name)
async def fsm_last_name(message: Message, state: FSMContext):
    last_name = message.text.strip()
    
    is_valid, error = validate_name_part(last_name, "Фамилия")
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте снова (например: Иванов):")
        return
    
    await state.update_data(last_name=last_name)
    await state.set_state(OrderFSM.first_name)
    await message.answer("👤 Введите имя / Enter first name (например: Иван):")


@router.message(OrderFSM.first_name)
async def fsm_first_name(message: Message, state: FSMContext):
    first_name = message.text.strip()
    
    is_valid, error = validate_name_part(first_name, "Имя")
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте снова (например: Иван):")
        return
    
    await state.update_data(first_name=first_name)
    await state.set_state(OrderFSM.patronymic)
    await message.answer("👤 Введите отчество / Enter patronymic (или отправьте '-' если нет):")


@router.message(OrderFSM.patronymic)
async def fsm_patronymic(message: Message, state: FSMContext):
    patronymic = message.text.strip()
    
    if patronymic == '-':
        await state.update_data(patronymic='')
    else:
        is_valid, error = validate_name_part(patronymic, "Отчество")
        if not is_valid:
            await message.answer(f"❌ {error}\nПопробуйте снова (или отправьте '-' чтобы пропустить):")
            return
        await state.update_data(patronymic=patronymic)
    
    await state.set_state(OrderFSM.city)
    await message.answer("🏙️ Введите город / Enter city (например: Москва):")


@router.message(OrderFSM.city)
async def fsm_city(message: Message, state: FSMContext):
    city = message.text.strip()
    
    is_valid, error = validate_city(city)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте снова (например: Москва):")
        return
    
    await state.update_data(city=city)
    await state.set_state(OrderFSM.street)
    await message.answer("🛣️ Введите улицу / Enter street (например: ул. Ленина):")


@router.message(OrderFSM.street)
async def fsm_street(message: Message, state: FSMContext):
    street = message.text.strip()
    
    is_valid, error = validate_street(street)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте снова (например: ул. Ленина):")
        return
    
    await state.update_data(street=street)
    await state.set_state(OrderFSM.house)
    await message.answer("🏠 Введите номер дома / Enter house number (например: 15 или 15А):")


@router.message(OrderFSM.house)
async def fsm_house(message: Message, state: FSMContext):
    house = message.text.strip()
    
    is_valid, error = validate_house_number(house)
    if not is_valid:
        await message.answer(f"❌ {error}\nПопробуйте снова (например: 15 или 15А):")
        return
    
    await state.update_data(house=house)
    await state.set_state(OrderFSM.apartment)
    await message.answer("🚪 Введите номер квартиры / Enter apartment number (или отправьте '-' если частный дом):")


@router.message(OrderFSM.apartment)
async def fsm_apartment(message: Message, state: FSMContext):
    apartment = message.text.strip()
    
    if apartment == '-':
        await state.update_data(apartment='')
    else:
        is_valid, error = validate_apartment(apartment)
        if not is_valid:
            await message.answer(f"❌ {error}\nПопробуйте снова (или отправьте '-' если частный дом):")
            return
        await state.update_data(apartment=apartment)
    
    await state.set_state(OrderFSM.floor)
    await message.answer("📊 Введите этаж / Enter floor (или отправьте '-' если не знаете):")


@router.message(OrderFSM.floor)
async def fsm_floor(message: Message, state: FSMContext, client: Client):
    floor = message.text.strip()
    
    if floor == '-':
        await state.update_data(floor='')
    else:
        is_valid, error = validate_floor(floor)
        if not is_valid:
            await message.answer(f"❌ {error}\nПопробуйте снова (или отправьте '-' если не знаете):")
            return
        await state.update_data(floor=floor)
    
    data = await state.get_data()
    
    full_name_parts = [data.get('last_name', '')]
    if data.get('first_name'):
        full_name_parts.append(data.get('first_name'))
    if data.get('patronymic'):
        full_name_parts.append(data.get('patronymic'))
    full_name = ' '.join(full_name_parts)
    
    address_parts = [
        f"г. {data.get('city', '')}",
        f"ул. {data.get('street', '')}",
        f"д. {data.get('house', '')}"
    ]
    if data.get('apartment'):
        address_parts.append(f"кв. {data.get('apartment')}")
    if data.get('floor'):
        address_parts.append(f"эт. {data.get('floor')}")
    full_address = ', '.join(address_parts)

    lines, total_items = await get_cart_lines(client.id, 0)
    cart_text, total_sum = render_cart(lines, page=0, total=total_items)
    
    summary = (
        "📋 Подтверждение заказа / Order confirmation\n\n"
        f"👤 ФИО: {full_name}\n"
        f"📍 Адрес: {full_address}\n"
        f"📞 Телефон: {client.phone_number or 'не указан'}\n\n"
        f"{cart_text}"
    )
    
    await state.update_data(full_name=full_name, full_address=full_address)
    await state.set_state(OrderFSM.confirmation)
    await message.answer(summary, reply_markup=confirm_kb())


@router.callback_query(F.data == "order_edit")
async def fsm_edit(cb: CallbackQuery, state: FSMContext):
    await state.set_state(OrderFSM.last_name)
    await cb.message.answer("👤 Введите фамилию заново / Enter last name again:")
    await cb.answer()


@router.callback_query(F.data == "order_confirm")
async def fsm_confirm(cb: CallbackQuery, state: FSMContext, client: Client):
    data = await state.get_data()
    order_id = await _create_order(client, data.get("full_name", ""), data.get("full_address", ""))
    if not order_id:
        await cb.message.answer("❌ Корзина пуста / Cart is empty.")
        await state.clear()
        await cb.answer()
        return

    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил / I paid", callback_data=f"pay:{order_id}")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data=f"cancel_order_{order_id}")]
    ])

    bot_username = (await cb.bot.get_me()).username
    await cb.message.answer(
        f"✅ Заказ создан #{order_id}.\n"
        f"Статус: ожидает оплаты.\n\n"
        f"🔗 Ссылка на заказ: https://t.me/{bot_username}?start=order_{order_id}",
        reply_markup=cancel_kb,
    )

    await _notify_admin_new_order(cb.bot, order_id, client)
    await state.clear()
    await cb.answer()


@router.callback_query(F.data == "order_edit_cancel")
async def fsm_edit_cancel(cb: CallbackQuery, state: FSMContext, client: Client):
    """Отмена редактирования заказа"""
    await state.clear()
    await cb.message.answer("❌ Редактирование отменено")
    
    from app.handlers.cart import _show_cart
    await _show_cart(cb.message, client, 0)
    await cb.answer()


@router.callback_query(F.data == "order_edit")
async def fsm_edit(cb: CallbackQuery, state: FSMContext):
    """Редактирование заказа (было)"""
    data = await state.get_data()
    current_fio = f"{data.get('last_name', '')} {data.get('first_name', '')} {data.get('patronymic', '')}".strip()
    
    edit_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ФИО", callback_data="edit_fio")],
        [InlineKeyboardButton(text="✏️ Адрес", callback_data="edit_address")],
        [InlineKeyboardButton(text="❌ Отменить заказ", callback_data="order_edit_cancel")]
    ])
    
    await cb.message.answer(
        f"📝 *Что хотите изменить?*\n\n"
        f"Текущие данные:\n"
        f"👤 ФИО: {current_fio}\n"
        f"📍 Адрес: {data.get('full_address', '')}",
        reply_markup=edit_kb,
        parse_mode="Markdown"
    )
    await cb.answer()


@router.callback_query(F.data == "edit_fio")
async def edit_fio(cb: CallbackQuery, state: FSMContext):
    """Редактирование ФИО"""
    await state.set_state(OrderFSM.last_name)
    await cb.message.answer("👤 Введите фамилию заново:")
    await cb.answer()


@router.callback_query(F.data == "edit_address")
async def edit_address(cb: CallbackQuery, state: FSMContext):
    """Редактирование адреса"""
    await state.set_state(OrderFSM.city)
    await cb.message.answer("🏙️ Введите город заново:")
    await cb.answer()


@router.callback_query(F.data.startswith("pay:"))
async def mark_paid(cb: CallbackQuery, client: Client):
    try:
        order_id = int(cb.data.split(":", 1)[1])
    except Exception:
        await cb.answer("Bad data", show_alert=True)
        return

    async with SessionFactory() as s:
        await s.execute(update(Order).where(Order.id == order_id, Order.client_id == client.id).values(status="paid"))
        await s.commit()

    await cb.message.answer("✅ Оплата отмечена. Спасибо! / Payment marked as paid. Thank you!")
    await cb.answer()


@router.callback_query(F.data.startswith("cancel_order_"))
async def cancel_order(cb: CallbackQuery, client: Client):
    """Отмена заказа пользователем"""
    try:
        order_id = int(cb.data.split("_")[2])
    except Exception:
        await cb.answer("Ошибка", show_alert=True)
        return
    
    async with SessionFactory() as s:
        res = await s.execute(
            select(Order).where(Order.id == order_id, Order.client_id == client.id)
        )
        order = res.scalar_one_or_none()
        
        if not order:
            await cb.answer("Заказ не найден", show_alert=True)
            return
        
        if order.status != "pending_payment":
            await cb.answer("Этот заказ уже нельзя отменить", show_alert=True)
            return
        
        await s.execute(
            update(Order)
            .where(Order.id == order_id)
            .values(status="cancelled")
        )
        await s.commit()
    
    await cb.message.edit_text(
        f"❌ Заказ #{order_id} отменён",
        reply_markup=None
    )
    await cb.answer("Заказ отменён", show_alert=True)