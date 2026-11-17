from django.contrib import admin
from .models import Category, Product, ProductImage, Page, Order, OrderItem

admin.site.site_header = "Микродизайн · управление магазином"
admin.site.site_title = "Микродизайн"


class ImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "sku",
        "category",
        "price",
        "available",
        "active",
        "featured",
    ]
    list_filter = ["category", "available", "active", "featured"]
    search_fields = ["title", "sku", "description"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [ImageInline]
    list_per_page = 30


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "parent", "position"]
    list_select_related = ["parent"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "updated_at"]


class ItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "title", "sku", "price", "quantity"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "full_name",
        "status",
        "subtotal",
        "shipping_cost",
        "created_at",
    ]
    list_filter = ["status", "delivery"]
    search_fields = ["email", "full_name", "tracking"]
    readonly_fields = [
        "user",
        "full_name",
        "email",
        "phone",
        "delivery",
        "address",
        "comment",
        "subtotal",
        "consent_at",
        "created_at",
        "paid_at",
    ]
    inlines = [ItemInline]

    def has_add_permission(self, request):
        return False
