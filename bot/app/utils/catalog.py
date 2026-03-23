from __future__ import annotations

import logging
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, WebAppInfo
from sqlalchemy import func, select

from app.callbacks import AddToCartCb, AddToWishlistCb, CategoryCb, ProductCb, ProductsPageCb
from app.config import settings
from app.database import SessionFactory
from app.models import Category, Product, ProductImage

logger = logging.getLogger(__name__)

PAGE_SIZE = 5

async def get_root_categories() -> list[Category]:
    async with SessionFactory() as s:
        res = await s.execute(
            select(Category).where(Category.parent_id.is_(None)).order_by(Category.order, Category.name)
        )
        return list(res.scalars().all())


async def get_category(category_id: int) -> Category | None:
    async with SessionFactory() as s:
        res = await s.execute(select(Category).where(Category.id == category_id))
        return res.scalar_one_or_none()


async def get_child_categories(category_id: int) -> list[Category]:
    async with SessionFactory() as s:
        res = await s.execute(
            select(Category).where(Category.parent_id == category_id).order_by(Category.order, Category.name)
        )
        return list(res.scalars().all())


async def count_products(category_id: int) -> int:
    async with SessionFactory() as s:
        res = await s.execute(select(func.count(Product.id)).where(Product.category_id == category_id))
        return int(res.scalar_one())


async def get_products_page(category_id: int, page: int) -> list[Product]:
    category = await get_category(category_id)
    if category and await get_child_categories(category_id):
        return []
    
    offset = max(page, 0) * PAGE_SIZE
    async with SessionFactory() as s:
        res = await s.execute(
            select(Product)
            .where(Product.category_id == category_id)
            .order_by(Product.id.desc())
            .offset(offset)
            .limit(PAGE_SIZE)
        )
        return list(res.scalars().all())


async def get_product(product_id: int) -> Product | None:
    async with SessionFactory() as s:
        res = await s.execute(select(Product).where(Product.id == product_id))
        return res.scalar_one_or_none()


async def get_product_images(product_id: int) -> list[ProductImage]:
    async with SessionFactory() as s:
        res = await s.execute(
            select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.order, ProductImage.id)
        )
        return list(res.scalars().all())


def categories_kb(categories: list[Category]) -> InlineKeyboardMarkup:
    """Клавиатура с категориями"""
    rows = []
    for c in categories:
        emoji = "📁"
        if "электроник" in c.name.lower():
            emoji = "💻"
        elif "одежд" in c.name.lower():
            emoji = "👕"
        elif "книг" in c.name.lower():
            emoji = "📚"
        elif "дом" in c.name.lower():
            emoji = "🏠"
            
        rows.append([
            InlineKeyboardButton(
                text=f"{emoji} {c.name}", 
                callback_data=CategoryCb(category_id=c.id).pack()
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_list_kb(category_id: int, products: list[Product], page: int, total: int) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру со списком товаров"""
    rows: list[list[InlineKeyboardButton]] = []
    
    if not products:
        rows.append([InlineKeyboardButton(
            text="📭 В этой категории пока нет товаров",
            callback_data="noop"
        )])
    else:
        for p in products:
            rows.append([InlineKeyboardButton(
                text=f"📦 {p.name[:30]}", 
                callback_data=ProductCb(product_id=p.id).pack()
            )])

    nav_row = []
    if total > 0:
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=ProductsPageCb(category_id=category_id, page=page - 1).pack()
            ))
        
        if total_pages > 1:
            nav_row.append(InlineKeyboardButton(
                text=f"📄 {page + 1}/{total_pages}",
                callback_data="noop"
            ))
        
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=ProductsPageCb(category_id=category_id, page=page + 1).pack()
            ))
        
        if nav_row:
            rows.append(nav_row)

    rows.append([InlineKeyboardButton(
        text="🏠 В корень каталога", 
        callback_data=CategoryCb(category_id=0).pack()
    )])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_kb(product_id: int) -> InlineKeyboardMarkup:
    webapp_url = f"{settings.WEBAPP_URL}/product/{product_id}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 В корзину", callback_data=AddToCartCb(product_id=product_id).pack())],
            [InlineKeyboardButton(text="⭐ В избранное", callback_data=AddToWishlistCb(product_id=product_id).pack())],
            [InlineKeyboardButton(text="🌐 Открыть WebApp", web_app=WebAppInfo(url=webapp_url))],
        ]
    )


def product_media(images: list[ProductImage]) -> list[InputMediaPhoto]:
    """Создает медиа-группу из изображений товара"""
    media: list[InputMediaPhoto] = []
    
    for img in images:
        url = _image_to_tg_media(img.image)
        logger.info(f"Processing image {img.id}, URL: {url}")
        
        if url and not url.lower().endswith('.webp'):
            media.append(InputMediaPhoto(media=url))
        else:
            logger.warning(f"Skipping image {img.id} - invalid format or URL: {url}")
    
    logger.info(f"Created media group with {len(media)} items")
    return media


def _image_to_tg_media(image_path: str) -> str:
    """Конвертирует путь к изображению в URL для Telegram"""
    import time
    
    if image_path.startswith("http://") or image_path.startswith("https://"):
        separator = '&' if '?' in image_path else '?'
        return f"{image_path}{separator}_={int(time.time())}"
    
    base = settings.DJANGO_BASE_URL
    if not base:
        logger.error("DJANGO_BASE_URL is not set")
        return ""
    base = base.rstrip("/")
    clean_path = image_path.lstrip('/')
    url = f"{base}/media/{clean_path}"
    url = f"{url}?_={int(time.time())}"
    
    return url