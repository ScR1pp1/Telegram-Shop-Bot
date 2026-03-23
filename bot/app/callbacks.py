from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class CategoryCb(CallbackData, prefix="cat"):
    category_id: int


class ProductsPageCb(CallbackData, prefix="plist"):
    category_id: int
    page: int


class ProductCb(CallbackData, prefix="prod"):
    product_id: int


class AddToCartCb(CallbackData, prefix="add"):
    product_id: int


class CartItemQtyCb(CallbackData, prefix="cqty"):
    cart_item_id: int
    delta: int


class CartClearCb(CallbackData, prefix="cclear"):
    ok: int = 1


class CartCheckoutCb(CallbackData, prefix="ccheck"):
    ok: int = 1


class CartPageCb(CallbackData, prefix="cpage"):
    page: int

class BackToCategoryCb(CallbackData, prefix="back"):
    category_id: int
    page: int = 0

class AddToWishlistCb(CallbackData, prefix="wish"):
    product_id: int
