from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils import timezone
from django.db import models
from django.urls import reverse


class Category(models.Model):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField(unique=True, max_length=200)
    position = models.PositiveIntegerField("Порядок", default=0)
    parent = models.ForeignKey("self", verbose_name="Родительский раздел", null=True, blank=True, on_delete=models.PROTECT, related_name="children")

    def clean(self):
        super().clean()
        ancestor = self.parent
        seen = set()
        while ancestor is not None:
            if ancestor.pk == self.pk and self.pk is not None or ancestor.pk in seen:
                raise ValidationError({"parent": "Раздел не может быть вложен в себя или своего потомка."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent

    class Meta:
        ordering = ["position", "name"]
        verbose_name = "Раздел"
        verbose_name_plural = "Разделы"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Раздел",
    )
    title = models.CharField("Название", max_length=500)
    slug = models.SlugField(max_length=240, unique=True)
    sku = models.CharField("Артикул", max_length=100, blank=True, db_index=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField(
        "Цена, ₽",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    scale = models.CharField("Масштаб", max_length=30, blank=True, db_index=True)
    manufacturer = models.CharField("Производитель", max_length=200, blank=True)
    active = models.BooleanField("Опубликован", default=True)
    available = models.BooleanField("Наличие подтверждено", default=False)
    featured = models.BooleanField("На главной", default=False)
    source_url = models.URLField(
        "Исходная карточка", unique=True, null=True, blank=True, max_length=1000
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("product", args=[self.slug])

    @property
    def cover(self):
        return self.images.all()[0] if self.images.all() else None


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField("Фотография", upload_to="products/%Y/%m")
    caption = models.CharField("Подпись", max_length=500, blank=True)
    position = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "Фотография"
        verbose_name_plural = "Фотографии"


class News(models.Model):
    title = models.CharField("Заголовок", max_length=250)
    slug = models.SlugField("Адрес", max_length=240, unique=True, allow_unicode=True)
    summary = models.TextField("Краткое описание", blank=True)
    body = models.TextField("Текст новости")
    image = models.ImageField("Изображение", upload_to="news/%Y/%m", blank=True)
    published = models.BooleanField("Опубликована", default=False)
    published_at = models.DateTimeField("Дата публикации", default=timezone.now)

    class Meta:
        ordering = ["-published_at", "-pk"]
        verbose_name = "Новость"
        verbose_name_plural = "Новости"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("news_detail", args=[self.slug])


class Banner(models.Model):
    title = models.CharField("Заголовок нижней панели", max_length=250)
    subtitle = models.CharField("Подпись нижней панели", max_length=250, blank=True)
    label = models.CharField("Верхняя подпись", max_length=150, blank=True, default="МИКРОДИЗАЙН / ИЗ КАТАЛОГА")
    overlay_text = models.CharField("Крупный текст поверх изображения", max_length=200, blank=True)
    image = models.ImageField("Изображение", upload_to="banners/%Y/%m")
    image_alt = models.CharField("Описание изображения", max_length=250, blank=True)
    show_grid = models.BooleanField("Показывать сетку", default=True)
    product = models.ForeignKey(Product, verbose_name="Ссылка на товар", null=True, blank=True, on_delete=models.SET_NULL)
    news = models.ForeignKey(News, verbose_name="Ссылка на новость", null=True, blank=True, on_delete=models.SET_NULL)
    link_url = models.CharField("Другой адрес ссылки", max_length=2000, blank=True, help_text="Внутренний адрес с / или полный адрес https://…")
    position = models.PositiveIntegerField("Порядок", default=0)
    active = models.BooleanField("Показывать", default=True)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = "Баннер"
        verbose_name_plural = "Баннерная карусель"

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if sum(bool(x) for x in (self.product_id, self.news_id, self.link_url)) > 1:
            raise ValidationError("Выберите только один вариант ссылки: товар, новость или другой адрес.")
        if self.link_url:
            if self.link_url.startswith("/") and not self.link_url.startswith("//") and "\\" not in self.link_url and not any(c.isspace() for c in self.link_url):
                return
            try:
                URLValidator(schemes=["http", "https"])(self.link_url)
            except ValidationError:
                raise ValidationError({"link_url": "Укажите адрес, начинающийся с /, http:// или https://."})

    @property
    def target_url(self):
        if self.product_id and self.product.active:
            return self.product.get_absolute_url()
        if self.news_id and self.news.published and self.news.published_at <= timezone.now():
            return self.news.get_absolute_url()
        return self.link_url


class Page(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField("Заголовок", max_length=200)
    body = models.TextField("Текст (абзацы через пустую строку)")
    source_url = models.URLField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Информационная страница"
        verbose_name_plural = "Информационные страницы"

    def __str__(self):
        return self.title


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Ожидает подтверждения"
        READY = "ready", "Ожидает оплаты"
        PAID = "paid", "Оплачен"
        SHIPPED = "shipped", "Отправлен"
        CANCELLED = "cancelled", "Отменён"

    checkout_key = models.UUIDField(unique=True, null=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    full_name = models.CharField("ФИО", max_length=250)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=40)
    delivery = models.CharField(
        "Доставка",
        max_length=30,
        choices=[
            ("post_letter", "Почта России — бандероль"),
            ("post_parcel", "Почта России — посылка"),
            ("cdek", "СДЭК — пункт выдачи"),
        ],
    )
    address = models.TextField("Адрес / ПВЗ")
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW
    )
    subtotal = models.DecimalField("Товары, ₽", max_digits=12, decimal_places=2)
    shipping_cost = models.DecimalField(
        "Доставка, ₽",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    tracking = models.CharField("Трек-номер", max_length=150, blank=True)
    consent_at = models.DateTimeField("Согласие с условиями", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

    def __str__(self):
        return f"МД-{self.pk:06d}"

    @property
    def total(self):
        return Decimal(self.subtotal) + Decimal(self.shipping_cost or "0")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    title = models.CharField(max_length=500)
    sku = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    @property
    def total(self):
        return self.price * self.quantity
