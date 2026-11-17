from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from .admin_forms import BannerAdminForm
from .models import Category, Product, ProductImage, Page, Order, OrderItem, News, Banner

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


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ["title", "published", "published_at"]
    list_filter = ["published"]
    search_fields = ["title", "body"]
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    form = BannerAdminForm
    list_display = ["title", "position", "active", "show_grid"]
    list_editable = ["position", "active"]
    list_filter = ["active"]
    search_fields = ["title"]
    autocomplete_fields = ["product", "news"]
    fieldsets = (
        ("Ссылка — выберите один вариант", {"fields": ("product", "news", "link_url")}),
        ("Содержимое", {"fields": ("title", "subtitle", "label", "overlay_text", "image", "product_image_id", "news_image_id", "image_alt", "show_grid")}),
        ("Публикация", {"fields": ("active", "position")}),
    )

    class Media:
        js = ("shop/admin-banner-v3.js",)
        css = {"all": ("shop/admin-banner.css",)}

    def get_urls(self):
        return [path("source/", self.admin_site.admin_view(self.source), name="shop_banner_source")] + super().get_urls()

    def source(self, request):
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            return JsonResponse({"error": "Доступ запрещён"}, status=403)
        kind = request.GET.get("type")
        pk = request.GET.get("id", "")
        if not pk.isdigit():
            return JsonResponse({"error": "Не найдено"}, status=404)
        if kind == "product" and self.admin_site._registry[Product].has_view_permission(request):
            item = Product.objects.filter(pk=pk).prefetch_related("images").first()
            if item:
                return JsonResponse({"title": item.title, "subtitle": " · ".join(filter(None, [item.sku, item.scale])), "images": [{"id": photo.pk, "url": photo.image.url, "caption": photo.caption or item.title} for photo in item.images.all() if photo.image]})
        if kind == "news" and self.admin_site._registry[News].has_view_permission(request):
            item = News.objects.filter(pk=pk).first()
            if item:
                return JsonResponse({"title": item.title, "summary": item.summary, "image": item.image.url if item.image else ""})
        return JsonResponse({"error": "Не найдено"}, status=404)



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
