from __future__ import annotations

import logging
import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from sqlalchemy import insert, select, update

from app.callbacks import AddToCartCb, AddToWishlistCb, CategoryCb, ProductCb, ProductsPageCb, BackToCategoryCb
from app.database import SessionFactory
from app.models import CartItem, Client, WishlistItem
from app.utils.catalog import (
    categories_kb,
    count_products,
    get_product,
    get_product_images,
    get_products_page,
    product_card_kb,
    product_media,
    products_list_kb,
    _image_to_tg_media,
    get_category,
    PAGE_SIZE,
)
from app.utils.cache import category_cache

logger = logging.getLogger("bot.catalog")

router = Router()


@router.message(Command("catalog"))
async def catalog_cmd(message: Message):
    """Обработчик команды /catalog"""
    try:
        cats = await category_cache.get_root_categories()
        if not cats:
            logger.warning(f"Catalog is empty for user {message.from_user.id}")
            await message.answer("📭 *Каталог пуст*\n\nТовары появятся позже. Загляните позже!")
            return
        
        logger.info(f"User {message.from_user.id} opened catalog")
        await message.answer(
            "📋 *Категории товаров*\n\nВыберите категорию:",
            reply_markup=categories_kb(cats)
        )
    except Exception as e:
        logger.error(f"Error in catalog_cmd: {e}", exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")


@router.callback_query(CategoryCb.filter())
async def category_clicked(cb: CallbackQuery, callback_data: CategoryCb):
    """Обработчик клика по категории"""
    try:
        logger.info(f"User {cb.from_user.id} clicked category {callback_data.category_id}")
                
        if callback_data.category_id == 0:  # root
            cats = await category_cache.get_root_categories()
            await cb.message.edit_text(
                "📋 *Категории товаров*\n\nВыберите категорию:",
                reply_markup=categories_kb(cats)
            )
            await cb.answer()
            return

        children = await category_cache.get_child_categories(callback_data.category_id)
        if children:
            await cb.message.edit_text(
                "📂 *Подкатегории*\n\nВыберите подкатегорию:",
                reply_markup=categories_kb(children)
            )
            await cb.answer()
            return

        total = await count_products(callback_data.category_id)
        if total == 0:
            cat = await category_cache.get_category(callback_data.category_id)
            cat_name = cat.name if cat else callback_data.category_id
            logger.info(f"Category {cat_name} is empty")
            
            parent_id = cat.parent_id if cat and hasattr(cat, 'parent_id') else 0
            await cb.message.edit_text(
                f"📭 *В категории {cat_name} пока нет товаров*",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data=CategoryCb(category_id=parent_id).pack())],
                    [InlineKeyboardButton(text="🏠 В корень", callback_data=CategoryCb(category_id=0).pack())]
                ])
            )
            await cb.answer()
            return

        products = await get_products_page(callback_data.category_id, page=0)
        await cb.message.edit_text(
            f"🛍️ *Товары в категории*\n\nСтраница 1 из {(total + PAGE_SIZE - 1) // PAGE_SIZE}:",
            reply_markup=products_list_kb(callback_data.category_id, products, page=0, total=total)
        )
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Error in category_clicked: {e}", exc_info=True)
        await cb.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(ProductsPageCb.filter())
async def products_page(cb: CallbackQuery, callback_data: ProductsPageCb):
    """Обработчик пагинации товаров"""
    try:
        total = await count_products(callback_data.category_id)
        products = await get_products_page(callback_data.category_id, page=callback_data.page)
        
        current_page = callback_data.page + 1
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        
        await cb.message.edit_text(
            f"🛍️ *Товары в категории*\n\nСтраница {current_page} из {total_pages}:",
            reply_markup=products_list_kb(callback_data.category_id, products, page=callback_data.page, total=total)
        )
        await cb.answer()
    except Exception as e:
        logger.error(f"Error in products_page: {e}", exc_info=True)
        await cb.answer("❌ Произошла ошибка", show_alert=True)


@router.callback_query(ProductCb.filter())
async def product_clicked(cb: CallbackQuery, callback_data: ProductCb):
    try:
        p = await get_product(callback_data.product_id)
        if not p:
            await cb.answer("Товар не найден", show_alert=True)
            return
        
        imgs = await get_product_images(p.id)
        product_text = f"*{p.name}*\n\n{p.description}\n\nЦена: {p.price} ₽"
        
        if imgs:
            first_url = _image_to_tg_media(imgs[0].image)
            await cb.message.answer_photo(
                photo=first_url,
                caption=product_text,
                parse_mode="Markdown",
                reply_markup=product_card_kb(p.id)
            )
            if len(imgs) > 1:
                remaining = imgs[1:]
                media_group = []
                for img in remaining:
                    url = _image_to_tg_media(img.image)
                    if url:
                        media_group.append(InputMediaPhoto(media=url))
                if media_group:
                    await cb.message.answer_media_group(media_group)
        else:
            await cb.message.answer(
                product_text,
                reply_markup=product_card_kb(p.id),
                parse_mode="Markdown",
            )
        
        try:
            await cb.message.delete()
        except:
            pass
        
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Error in product_clicked: {e}", exc_info=True)
        await cb.message.answer("Произошла ошибка при загрузке товара")
        await cb.answer()


@router.callback_query(BackToCategoryCb.filter())
async def back_to_category(cb: CallbackQuery, callback_data: BackToCategoryCb):
    """Обработчик возврата к категории"""
    try:
        total = await count_products(callback_data.category_id)
        if total == 0:
            cat = await category_cache.get_category(callback_data.category_id)
            if cat and cat.parent_id:
                await cb.message.edit_text(
                    f"📂 *Подкатегории*\n\nВыберите подкатегорию:",
                    reply_markup=categories_kb(await category_cache.get_child_categories(cat.parent_id))
                )
            else:
                cats = await category_cache.get_root_categories()
                await cb.message.edit_text(
                    "📋 *Категории товаров*\n\nВыберите категорию:",
                    reply_markup=categories_kb(cats)
                )
            await cb.answer()
            return
        
        products = await get_products_page(callback_data.category_id, page=callback_data.page)
        await cb.message.edit_text(
            f"🛍️ *Товары в категории*\n\nСтраница {callback_data.page + 1} из {(total + PAGE_SIZE - 1) // PAGE_SIZE}:",
            reply_markup=products_list_kb(callback_data.category_id, products, page=callback_data.page, total=total)
        )
        await cb.answer()
        
    except Exception as e:
        logger.error(f"Error in back_to_category: {e}", exc_info=True)
        await cb.answer("Произошла ошибка", show_alert=True)


@router.callback_query(AddToCartCb.filter())
async def add_to_cart(cb: CallbackQuery, callback_data: AddToCartCb, client: Client):
    """Обработчик добавления в корзину с кнопкой продолжения"""
    try:
        async with SessionFactory() as s:
            res = await s.execute(
                select(CartItem).where(
                    CartItem.client_id == client.id, 
                    CartItem.product_id == callback_data.product_id
                )
            )
            item = res.scalar_one_or_none()
            
            if item:
                await s.execute(
                    update(CartItem)
                    .where(CartItem.id == item.id)
                    .values(quantity=item.quantity + 1)
                )
                await s.commit()
                quantity = item.quantity + 1
            else:
                await s.execute(
                    insert(CartItem).values(
                        client_id=client.id, 
                        product_id=callback_data.product_id, 
                        quantity=1
                    )
                )
                await s.commit()
                quantity = 1
        
        continue_kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🛒 В корзину", callback_data="go_to_cart"),
                InlineKeyboardButton(text="📋 В каталог", callback_data="back_to_catalog")
            ],
            [
                InlineKeyboardButton(text="➡️ Продолжить покупки", callback_data="continue_shopping")
            ]
        ])
        
        await cb.message.answer(
            f"Товар добавлен в корзину! (теперь {quantity} шт.)",
            reply_markup=continue_kb
        )
        
        try:
            await cb.message.delete()
        except:
            pass
            
        await cb.answer()
            
    except Exception as e:
        logger.error(f"Error in add_to_cart: {e}", exc_info=True)
        await cb.answer("Ошибка при добавлении", show_alert=True)


@router.callback_query(F.data == "go_to_cart")
async def go_to_cart(cb: CallbackQuery, client: Client):
    """Переход в корзину"""
    from app.handlers.cart import _show_cart
    await _show_cart(cb.message, client, 0)
    await cb.answer()


@router.callback_query(F.data == "back_to_catalog")
async def back_to_catalog(cb: CallbackQuery):
    """Возврат в каталог"""
    from app.handlers.catalog import catalog_cmd
    await catalog_cmd(cb.message)
    await cb.answer()


@router.callback_query(F.data == "continue_shopping")
async def continue_shopping(cb: CallbackQuery):
    """Продолжить покупки (удаляет сообщение)"""
    try:
        await cb.message.delete()
    except:
        pass
    await cb.answer()


@router.callback_query(AddToWishlistCb.filter())
async def add_to_wishlist(cb: CallbackQuery, callback_data: AddToWishlistCb, client: Client):
    async with SessionFactory() as s:
        res = await s.execute(
            select(WishlistItem).where(
                WishlistItem.client_id == client.id,
                WishlistItem.product_id == callback_data.product_id
            )
        )
        if res.scalar_one_or_none():
            await cb.answer("✅ Уже в избранном", show_alert=False)
            return
        await s.execute(
            insert(WishlistItem).values(
                client_id=client.id,
                product_id=callback_data.product_id
            )
        )
        await s.commit()
    await cb.answer("⭐ Добавлено в избранное", show_alert=False)