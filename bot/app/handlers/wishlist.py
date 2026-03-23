from __future__ import annotations

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select, delete

from app.database import SessionFactory
from app.models import Client, WishlistItem, Product
from app.callbacks import AddToCartCb

logger = logging.getLogger("bot.wishlist")
router = Router()


@router.message(Command("wishlist"))
async def wishlist_cmd(message: Message, client: Client):
    async with SessionFactory() as s:
        res = await s.execute(
            select(WishlistItem, Product)
            .join(Product, Product.id == WishlistItem.product_id)
            .where(WishlistItem.client_id == client.id)
            .order_by(WishlistItem.created_at.desc())
        )
        items = res.all()

    if not items:
        await message.answer("⭐ У вас пока нет избранных товаров")
        return

    text = "⭐ *Ваше избранное:*\n\n"
    buttons = []
    for item, product in items:
        text += f"• {product.name} — {product.price} ₽\n"
        buttons.append([
            InlineKeyboardButton(
                text=f"🛒 Купить {product.name}",
                callback_data=AddToCartCb(product_id=product.id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=f"remove_wish_{item.id}"
            )
        ])

    await message.answer(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


@router.callback_query(F.data.startswith("remove_wish_"))
async def remove_wish(cb: CallbackQuery, client: Client):
    item_id = int(cb.data.split("_")[2])
    async with SessionFactory() as s:
        await s.execute(delete(WishlistItem).where(WishlistItem.id == item_id, WishlistItem.client_id == client.id))
        await s.commit()
    await cb.answer("❌ Удалено из избранного")
    await wishlist_cmd(cb.message, client)