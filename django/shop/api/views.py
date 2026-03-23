from __future__ import annotations

from decimal import Decimal

from django.db import transaction, IntegrityError
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from shop.models import CartItem, Category, Order, OrderItem, Product, WishlistItem

from .permissions import IsTelegramClient
from .serializers import (
    CartItemSerializer,
    CategorySerializer,
    OrderCreateSerializer,
    OrderSerializer,
    ProductSerializer,
    WishlistItemSerializer,
)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        return {'request': self.request}


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.all().prefetch_related("images")
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get("category")
        search = self.request.query_params.get("search")
        if category:
            qs = qs.filter(category_id=category)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsTelegramClient]

    def get_queryset(self):
        return CartItem.objects.filter(client=self.request.user).select_related("product").prefetch_related("product__images")

    def perform_create(self, serializer):
        try:
            serializer.save(client=self.request.user)
        except IntegrityError:
            product_id = serializer.validated_data['product'].id
            cart_item = CartItem.objects.get(client=self.request.user, product_id=product_id)
            cart_item.quantity += 1
            cart_item.save()
            serializer.instance = cart_item

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OrderViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsTelegramClient]

    def get_queryset(self):
        return (
            Order.objects.filter(client=self.request.user)
            .prefetch_related("items__product__images")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cart_items = list(
            CartItem.objects.select_related("product").filter(client=request.user)
        )
        if not cart_items:
            return Response({"detail": "Cart is empty"}, status=400)

        total = Decimal("0.00")
        for ci in cart_items:
            total += ci.product.price * ci.quantity

        order = Order.objects.create(
            client=request.user,
            full_name=serializer.validated_data["full_name"],
            address=serializer.validated_data["address"],
            phone=serializer.validated_data.get("phone") or (request.user.phone_number or ""),
            total=total,
            status="pending_payment",
        )

        OrderItem.objects.bulk_create(
            [
                OrderItem(
                    order=order,
                    product=ci.product,
                    quantity=ci.quantity,
                    price=ci.product.price,
                )
                for ci in cart_items
            ]
        )
        CartItem.objects.filter(client=request.user).delete()

        out = OrderSerializer(order, context=self.get_serializer_context()).data
        return Response(out, status=201)

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        order = self.get_object()
        order.status = "paid"
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order, context=self.get_serializer_context()).data)


class WishlistItemViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [IsTelegramClient]

    def get_queryset(self):
        return WishlistItem.objects.filter(client=self.request.user).select_related("product")

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            return Response(
                {"detail": "Товар уже в избранном"},
                status=status.HTTP_400_BAD_REQUEST
            )

    def perform_create(self, serializer):
        serializer.save(client=self.request.user)