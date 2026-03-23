from __future__ import annotations

from django.contrib import admin
from django import forms
from django.db.models import Count, Sum
from django.http import HttpRequest, HttpResponse
from openpyxl import Workbook

from .models import (
    CartItem,
    Category,
    Channel,
    Client,
    Faq,
    Mailing,
    Order,
    OrderItem,
    Product,
    ProductImage,
    Setting,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "telegram_id",
        "username",
        "phone_number",
        "is_admin",
        "is_active",
        "num_orders",
        "total_spent",
        "created_at",
    )
    search_fields = ("telegram_id", "username", "phone_number")
    list_filter = ("is_admin", "is_active")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(_num_orders=Count("orders"), _total_spent=Sum("orders__total"))

    @admin.display(ordering="_num_orders", description="Orders")
    def num_orders(self, obj: Client) -> int:
        return int(getattr(obj, "_num_orders", 0) or 0)

    @admin.display(ordering="_total_spent", description="Total spent")
    def total_spent(self, obj: Client):
        return getattr(obj, "_total_spent", None) or 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "parent", "order")
    search_fields = ("name", "slug")
    list_filter = ("parent",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        leaf_categories = Category.objects.filter(children__isnull=True)
        self.fields['category'].queryset = leaf_categories
        self.fields['category'].help_text = 'Только конечные категории (без подкатегорий)'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ("id", "name", "category", "price", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("category",)
    inlines = [ProductImageInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "product", "quantity")
    search_fields = ("client__telegram_id", "product__name")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price")
    can_delete = False


@admin.action(description="Export paid orders to Excel")
def export_paid_orders_to_excel(modeladmin: admin.ModelAdmin, request: HttpRequest, queryset):
    wb = Workbook()
    ws = wb.active
    ws.title = "Paid Orders"

    ws.append(
        [
            "order_id",
            "created_at",
            "status",
            "total",
            "client_telegram_id",
            "full_name",
            "phone",
            "address",
        ]
    )
    for o in queryset.filter(status="paid").select_related("client"):
        ws.append(
            [
                o.id,
                o.created_at.isoformat(),
                o.status,
                str(o.total),
                o.client.telegram_id,
                o.full_name,
                o.phone,
                o.address,
            ]
        )

    resp = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    resp["Content-Disposition"] = 'attachment; filename="paid_orders.xlsx"'
    wb.save(resp)
    return resp


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "client", "total", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("client__telegram_id", "client__username", "full_name", "phone")
    inlines = [OrderItemInline]
    actions = [export_paid_orders_to_excel]


@admin.register(Faq)
class FaqAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "is_active", "order")
    list_filter = ("is_active",)
    search_fields = ("question", "answer")


@admin.action(description="Mark selected mailings as ready")
def mailings_mark_ready(modeladmin: admin.ModelAdmin, request: HttpRequest, queryset):
    queryset.update(status="ready")


@admin.register(Mailing)
class MailingAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "status", "stats_sent", "stats_failed", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "text")
    actions = [mailings_mark_ready]


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("id", "channel_id", "title")
    search_fields = ("channel_id", "title")


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "value")
    search_fields = ("key", "value")