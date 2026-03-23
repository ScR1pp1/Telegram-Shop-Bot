from __future__ import annotations

from rest_framework import serializers

from shop.models import CartItem, Category, Order, OrderItem, Product, ProductImage, WishlistItem


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "order")


class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ("id", "category", "name", "description", "price", "images")


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    has_products = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "parent", "image", "order", "children", "has_products")

    def get_image(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                url = request.build_absolute_uri(obj.image.url)
                https_url = url.replace('http://', 'https://')
                return https_url.replace('localhost:8000', 'telegram-shop-api.loca.lt')
        return None

    def get_children(self, obj: Category):
        qs = obj.get_children().all()
        return CategorySerializer(qs, many=True, context=self.context).data

    def get_has_products(self, obj):
        def _has_products(cat):
            if cat.products.exists():
                return True
            for child in cat.get_children():
                if _has_products(child):
                    return True
            return False
        return _has_products(obj)


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all(), write_only=True
    )

    class Meta:
        model = CartItem
        fields = ("id", "product", "product_id", "quantity")


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ("id", "product", "quantity", "price")


class OrderCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ("id", "full_name", "address", "phone")

    def validate(self, attrs):
        if not attrs.get("full_name"):
            raise serializers.ValidationError({"full_name": "Required"})
        if not attrs.get("address"):
            raise serializers.ValidationError({"address": "Required"})
        return attrs


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "full_name", "address", "phone", "total", "status", "created_at", "items")


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all(), write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ("id", "product", "product_id", "created_at")