from __future__ import annotations

import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from app.callbacks import (
    CartCheckoutCb, 
    CartClearCb, 
    CartItemQtyCb,
    CartPageCb
)
from app.models import Client
from app.states.order import OrderFSM
from app.utils.cart import (
    cart_kb, 
    change_qty, 
    clear_cart, 
    get_cart_lines, 
    render_cart,
    CART_PAGE_SIZE
)

logger = logging.getLogger("bot.cart")
router = Router()


async def _show_cart(message: Message, client: Client, page: int = 0):
    """Показать корзину с пагинацией"""
    lines, total = await get_cart_lines(client.id, page)
    text, _ = render_cart(lines, page, total)
    
    if not lines and page > 0:
        await _show_cart(message, client, 0)
        return
        
    await message.answer(text, reply_markup=cart_kb(lines, page, total))


@router.message(Command("cart"))
async def cart_cmd(message: Message, client: Client):
    """Обработчик команды /cart"""
    logger.info(f"User {client.telegram_id} opened cart")
    await _show_cart(message, client, 0)


@router.callback_query(CartPageCb.filter())
async def cart_page(cb: CallbackQuery, callback_data: CartPageCb, client: Client):
    """Обработчик пагинации корзины"""
    logger.info(f"User {client.telegram_id} navigated to cart page {callback_data.page}")
    lines, total = await get_cart_lines(client.id, callback_data.page)
    text, _ = render_cart(lines, callback_data.page, total)
    
    if cb.message:
        await cb.message.edit_text(text, reply_markup=cart_kb(lines, callback_data.page, total))
    await cb.answer()


@router.callback_query(CartItemQtyCb.filter())
async def cart_qty(cb: CallbackQuery, callback_data: CartItemQtyCb, client: Client):
    """Обработчик изменения количества"""
    logger.info(f"User {client.telegram_id} changed quantity for item {callback_data.cart_item_id} by {callback_data.delta}")
    await change_qty(callback_data.cart_item_id, callback_data.delta)
    
    lines, total = await get_cart_lines(client.id, 0)
    text, _ = render_cart(lines, 0, total)
    
    if cb.message:
        await cb.message.edit_text(text, reply_markup=cart_kb(lines, 0, total))
    await cb.answer()


@router.callback_query(CartClearCb.filter())
async def cart_clear(cb: CallbackQuery, callback_data: CartClearCb, client: Client):
    """Обработчик очистки корзины с подтверждением"""
    logger.info(f"User {client.telegram_id} initiated cart clear")
    
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, очистить", callback_data="confirm_clear_yes"),
            InlineKeyboardButton(text="❌ Нет, отмена", callback_data="confirm_clear_no")
        ]
    ])
    
    await cb.message.edit_text(
        "🗑️ *Подтверждение*\n\nВы уверены, что хотите очистить корзину?",
        reply_markup=confirm_kb,
        parse_mode="Markdown"
    )
    await cb.answer()


@router.callback_query(F.data == "confirm_clear_yes")
async def confirm_clear_yes(cb: CallbackQuery, client: Client):
    """Подтверждение очистки"""
    logger.info(f"User {client.telegram_id} confirmed cart clear")
    await clear_cart(client.id)
    await cb.message.edit_text("✅ Корзина очищена / Cart is empty.", reply_markup=None)
    await cb.answer("Очищено / Cleared")


@router.callback_query(F.data == "confirm_clear_no")
async def confirm_clear_no(cb: CallbackQuery, client: Client):
    """Отмена очистки"""
    logger.info(f"User {client.telegram_id} cancelled cart clear")
    
    lines, total = await get_cart_lines(client.id, 0)
    text, _ = render_cart(lines, 0, total)
    await cb.message.edit_text(text, reply_markup=cart_kb(lines, 0, total))
    await cb.answer("Отменено / Cancelled")


@router.callback_query(CartCheckoutCb.filter())
async def cart_checkout(cb: CallbackQuery, callback_data: CartCheckoutCb, state: FSMContext, client: Client):
    """Обработчик оформления заказа - теперь запускает FSM"""
    logger.info(f"User {client.telegram_id} started checkout from cart")
    
    lines, total = await get_cart_lines(client.id, 0)
    if not lines:
        await cb.answer("Корзина пуста / Cart is empty", show_alert=True)
        return
    
    await state.set_state(OrderFSM.last_name)
    
    if cb.message:
        try:
            await cb.message.delete()
        except:
            pass
        await cb.message.answer("👤 Введите фамилию / Enter last name (например: Иванов):")
    
    await cb.answer()