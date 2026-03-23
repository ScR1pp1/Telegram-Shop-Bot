from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CartItemViewSet, CategoryViewSet, OrderViewSet, ProductViewSet, WishlistItemViewSet
from .me import me

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="categories")
router.register("products", ProductViewSet, basename="products")
router.register("cart", CartItemViewSet, basename="cart")
router.register("orders", OrderViewSet, basename="orders")
router.register("wishlist", WishlistItemViewSet, basename="wishlist")

urlpatterns = [
    path("auth/me/", me),
    path("", include(router.urls)),
]

