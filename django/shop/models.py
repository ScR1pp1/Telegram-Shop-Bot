from __future__ import annotations

from django.db import models
from django.core.exceptions import ValidationError
from mptt.models import MPTTModel, TreeForeignKey
from model_utils import FieldTracker

from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import os

class Client(models.Model):
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.telegram_id} ({self.username or '-'})"


class Category(MPTTModel):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    parent = TreeForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    image = models.ImageField(upload_to="categories/", blank=True, null=True)
    order = models.PositiveIntegerField(default=0)

    class MPTTMeta:
        order_insertion_by = ["order", "name"]

    class Meta:
        ordering = ["order", "name"]

    @property
    def secure_image_url(self):
        """Возвращает HTTPS URL для изображения категории"""
        if self.image and self.image.url:
            return self.image.url.replace('http://', 'https://')
        return None

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Проверка, что категория не имеет детей и задана"""
        if not self.category_id:
            raise ValidationError({'category': 'Обязательно выберите категорию'})

        from .models import Category
        category = Category.objects.filter(id=self.category_id).first()
        if category and category.get_children().exists():
            raise ValidationError({
                'category': 'Нельзя добавлять товары в категорию, у которой есть подкатегории. Выберите конечную категорию.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    @property
    def secure_image_url(self):
        """Возвращает HTTPS URL для изображения товара"""
        if self.image and self.image.url:
            return self.image.url.replace('http://', 'https://')
        return None

    def save(self, *args, **kwargs):
        if self.image and self.image.name.endswith('.webp'):
            img = Image.open(self.image)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            
            new_name = self.image.name.replace('.webp', '.jpg')
            
            self.image.save(new_name, ContentFile(output.read()), save=False)
        
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Image {self.id} for {self.product_id}"


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending_payment", "Ожидает оплаты"),
        ("paid", "Оплачен"),
        ("processing", "В обработке"),
        ("shipped", "Отгружен"),
        ("delivered", "Доставлен"),
        ("cancelled", "Отменён"),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="orders")
    full_name = models.CharField(max_length=255)
    address = models.TextField()
    phone = models.CharField(max_length=20)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_payment")
    created_at = models.DateTimeField(auto_now_add=True)

    tracker = FieldTracker(fields=["status"])

    def __str__(self) -> str:
        return f"Order {self.id} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self) -> str:
        return f"OrderItem {self.id}"


class CartItem(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "product"], name="uniq_cart_client_product"),
        ]

    def __str__(self) -> str:
        return f"CartItem {self.id}"


class Faq(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return self.question


class Mailing(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("ready", "Готово к отправке"),
        ("sending", "Отправляется"),
        ("sent", "Отправлено"),
    ]

    subject = models.CharField(max_length=255)
    text = models.TextField()
    image = models.ImageField(upload_to="mailings/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    stats_sent = models.PositiveIntegerField(default=0)
    stats_failed = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.subject} ({self.status})"


class Channel(models.Model):
    channel_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    invite_link = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self) -> str:
        return self.title


class Setting(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.TextField()

    def __str__(self) -> str:
        return self.key


class WishlistItem(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="wishlist")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["client", "product"], name="uniq_wishlist_client_product")
        ]

    def __str__(self):
        return f"{self.client.id} - {self.product.name}"