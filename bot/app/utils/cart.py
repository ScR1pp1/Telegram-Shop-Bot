from __future__ import annotations

from decimal import Decimal
import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import delete, func, select, update

from app.callbacks import (
    CartCheckoutCb, 
    CartClearCb, 
    CartItemQtyCb,
    CartPageCb
)
from app.database import SessionFactory
from app.models import CartItem, Product

logger = logging.getLogger("bot.cart")
CART_PAGE_SIZE = 3


async def get_cart_lines(client_id: int, page: int = 0):
    """Получить товары из корзины с пагинацией"""
    offset = max(page, 0) * CART_PAGE_SIZE
    async with SessionFactory() as s:
        count_res = await s.execute(
            select(func.count(CartItem.id))
            .where(CartItem.client_id == client_id)
        )
        total = count_res.scalar_one()
        
        res = await s.execute(
            select(CartItem.id, CartItem.quantity, Product.id, Product.name, Product.price)
            .join(Product, Product.id == CartItem.product_id)
            .where(CartItem.client_id == client_id)
            .order_by(CartItem.id.asc())
            .offset(offset)
            .limit(CART_PAGE_SIZE)
        )
        items = res.all()
        
    return items, total


def render_cart(lines, page: int = 0, total: int = 0) -> tuple[str, Decimal]:
    """Отрисовать корзину"""
    total_price = Decimal("0.00")
    parts: list[str] = []
    
    for cart_item_id, qty, product_id, name, price in lines:
        line_total = price * qty
        total_price += line_total
        parts.append(f"- {name} × {qty} = {line_total}")
    
    if not parts:
        return ("Корзина пуста / Cart is empty.", total_price)
    
    text = "Корзина / Cart:\n\n" + "\n".join(parts)
    text += f"\n\nИтого / Total: {total_price}"
    
    if total > CART_PAGE_SIZE:
        current_page = page + 1
        total_pages = (total + CART_PAGE_SIZE - 1) // CART_PAGE_SIZE
        text += f"\n\nСтраница {current_page} из {total_pages}"
    
    return (text, total_price)


def cart_kb(lines, page: int = 0, total: int = 0) -> InlineKeyboardMarkup:
    """Создать клавиатуру корзины с пагинацией"""
    rows: list[list[InlineKeyboardButton]] = []
    
    for cart_item_id, qty, product_id, name, price in lines:
        rows.append(
            [
                InlineKeyboardButton(
                    text="➖", 
                    callback_data=CartItemQtyCb(cart_item_id=cart_item_id, delta=-1).pack()
                ),
                InlineKeyboardButton(
                    text=f"{name[:14]} ({qty})", 
                    callback_data="noop"
                ),
                InlineKeyboardButton(
                    text="➕", 
                    callback_data=CartItemQtyCb(cart_item_id=cart_item_id, delta=+1).pack()
                ),
            ]
        )

    if total > CART_PAGE_SIZE:
        nav_row = []
        total_pages = (total + CART_PAGE_SIZE - 1) // CART_PAGE_SIZE
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=CartPageCb(page=page-1).pack()
            ))
        
        nav_row.append(InlineKeyboardButton(
            text=f"📄 {page+1}/{total_pages}",
            callback_data="noop"
        ))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=CartPageCb(page=page+1).pack()
            ))
        
        rows.append(nav_row)

    if lines:
        rows.append([InlineKeyboardButton(
            text="🧹 Очистить / Clear", 
            callback_data=CartClearCb().pack()
        )])
        rows.append([InlineKeyboardButton(
            text="✅ Оформить заказ / Checkout", 
            callback_data=CartCheckoutCb().pack()
        )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def change_qty(cart_item_id: int, delta: int) -> None:
    async with SessionFactory() as s:
        res = await s.execute(select(CartItem).where(CartItem.id == cart_item_id))
        item = res.scalar_one_or_none()
        if not item:
            return
        new_qty = item.quantity + delta
        if new_qty <= 0:
            await s.execute(delete(CartItem).where(CartItem.id == cart_item_id))
        else:
            await s.execute(update(CartItem).where(CartItem.id == cart_item_id).values(quantity=new_qty))
        await s.commit()


async def clear_cart(client_id: int) -> None:
    async with SessionFactory() as s:
        await s.execute(delete(CartItem).where(CartItem.client_id == client_id))
        await s.commit()