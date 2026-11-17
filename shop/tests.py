from decimal import Decimal
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from django.test import TestCase, override_settings, Client
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from PIL import Image
from .models import Category, Product, ProductImage, Order, OrderItem, Page
from .payments import digest, payment_url


class StoreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Category.objects.create(name="Авиация 1:48", slug="air")
        cls.p = Product.objects.create(
            category=cls.cat,
            title="Ми-171 — основной набор",
            slug="mi171",
            sku="МД 048001",
            price=Decimal("450.50"),
            available=True,
        )
        cls.user = get_user_model().objects.create_user(
            username="customer", password="test-example-password"
        )
        cls.other = get_user_model().objects.create_user(
            username="another", password="test-example-password"
        )

    def add(self):
        return self.client.post(f"/cart/{self.p.pk}/", {"quantity": 2})

    def test_public_pages_and_cyrillic_search(self):
        for url in [
            "/",
            "/catalog/",
            "/cart/",
            "/products/mi171/",
            "/account/login/",
            "/account/signup/",
        ]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/catalog/", {"q": "МИ-171"}), self.p.title)
        self.assertNotContains(
            self.client.get("/catalog/", {"q": "несуществующий"}), self.p.title
        )

    def test_cart_accepts_post_only_and_clamps_quantity(self):
        self.assertEqual(self.client.get(f"/cart/{self.p.pk}/").status_code, 405)
        self.client.post(f"/cart/{self.p.pk}/", {"quantity": 100000})
        self.assertEqual(self.client.session["cart"][str(self.p.pk)], 99)

    def test_unknown_stock_not_sellable(self):
        self.p.available = False
        self.p.save()
        self.add()
        self.assertFalse(self.client.session.get("cart"))

    def test_cart_remove_and_reject_bad_quantity(self):
        self.add()
        self.assertContains(self.client.get("/cart/"), "901,00")
        self.assertEqual(
            self.client.post(f"/cart/{self.p.pk}/", {"quantity": "bad"}).status_code,
            400,
        )
        self.client.post(f"/cart/{self.p.pk}/", {"action": "remove"})
        self.assertEqual(self.client.session["cart"], {})

    def test_csrf_protects_cart(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(
            c.post(f"/cart/{self.p.pk}/", {"quantity": 1}).status_code, 403
        )

    def test_checkout_snapshots_current_server_price(self):
        self.client.force_login(self.user)
        self.add()
        self.client.get("/checkout/")
        token = self.client.session["checkout_key"]
        self.p.price = Decimal("500.25")
        self.p.save()
        data = {
            "full_name": "Иванов Иван Иванович",
            "email": "test@example.com",
            "phone": "+79000000000",
            "delivery": "cdek",
            "address": "Тестовый ПВЗ",
            "consent": True,
            "checkout_key": token,
            "subtotal": "1",
        }
        response = self.client.post("/checkout/", data)
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.subtotal, Decimal("1000.50"))
        self.assertEqual(order.items.get().price, Decimal("500.25"))
        self.assertEqual(order.status, "new")
        self.assertIsNotNone(order.consent_at)
        self.client.post("/checkout/", data)
        self.assertEqual(Order.objects.count(), 1)

    def test_checkout_rejects_missing_nonce(self):
        self.client.force_login(self.user)
        self.add()
        self.client.post(
            "/checkout/",
            {
                "full_name": "Иванов Иван Иванович",
                "email": "test@example.com",
                "phone": "123",
                "delivery": "cdek",
                "address": "ПВЗ",
                "consent": True,
            },
        )
        self.assertEqual(Order.objects.count(), 0)

    def test_another_customer_cannot_read_order(self):
        order = self.make_order()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f"/orders/{order.pk}/").status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/orders/{order.pk}/").status_code, 200)

    def make_order(self):
        return Order.objects.create(
            user=self.user,
            full_name="Иванов Иван Иванович",
            email="t@example.com",
            phone="123",
            delivery="cdek",
            address="ПВЗ",
            subtotal="450.50",
            shipping_cost="200",
            status="ready",
        )

    @override_settings(
        PAYMENTS_ENABLED=True,
        ROBOKASSA_LOGIN="demo",
        ROBOKASSA_PASSWORD1="one",
        ROBOKASSA_PASSWORD2="two",
        ROBOKASSA_HASH="sha256",
    )
    def test_payment_signature_amount_replay_and_shipping_status(self):
        order = self.make_order()
        self.assertIn("OutSum=650.50", payment_url(order))
        url = "/payments/robokassa/result/"
        self.assertEqual(
            self.client.post(
                url, {"InvId": order.pk, "OutSum": "650.50", "SignatureValue": "fake"}
            ).status_code,
            400,
        )
        bad = {
            "InvId": order.pk,
            "OutSum": "1",
            "SignatureValue": digest(f"1:{order.pk}:two"),
        }
        self.assertEqual(self.client.post(url, bad).status_code, 400)
        data = {
            "InvId": order.pk,
            "OutSum": "650.500000",
            "SignatureValue": digest(f"650.500000:{order.pk}:two"),
        }
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(url, data).content, f"OK{order.pk}".encode())
        order.refresh_from_db()
        paid = order.paid_at
        self.assertEqual(order.status, "paid")
        self.assertEqual(c.post(url, data).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.paid_at, paid)
        order.status = "shipped"
        order.save()
        self.assertEqual(c.post(url, data).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, "shipped")

    @override_settings(PAYMENTS_ENABLED=False)
    def test_payments_disabled_by_default(self):
        order = self.make_order()
        self.assertIsNone(payment_url(order))
        self.assertEqual(
            self.client.post(
                "/payments/robokassa/result/", {"InvId": order.pk}
            ).status_code,
            400,
        )

    def test_success_url_never_marks_order_paid(self):
        order = self.make_order()
        self.client.get("/payments/robokassa/success/", {"InvId": order.pk})
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")


class ImportTests(TestCase):
    def test_import_nested_categories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            categories = [
                {"name": "Э.В.М.", "path": "root", "source_url": "https://microdisign.ru/products/smola", "products": []},
                {"name": "Авиация", "path": "root/aviation", "source_url": "https://microdisign.ru/products/smola/aviation", "parent_source_url": "https://microdisign.ru/products/smola", "products": []},
                {"name": "1:72", "path": "root/aviation/72", "source_url": "https://microdisign.ru/products/smola/aviation/72", "parent_source_url": "https://microdisign.ru/products/smola/aviation", "products": []},
            ]
            (root / "catalog_metadata.json").write_text(json.dumps({"categories": categories}))
            call_command("import_catalog", str(root), verbosity=0)
            self.assertEqual(Category.objects.get(name="1:72").parent.parent.name, "Э.В.М.")
            call_command("import_catalog", str(root), verbosity=0)
            self.assertEqual(Category.objects.count(), 3)

    def test_import_images_idempotency_and_editor_changes(self):
        with TemporaryDirectory() as tmp, TemporaryDirectory() as media:
            root = Path(tmp)
            folder = root / "cat" / "item"
            folder.mkdir(parents=True)
            source = "https://microdisign.ru/products/cat/item"
            manifest = {
                "categories": [
                    {
                        "name": "Флот 1:350",
                        "path": "cat",
                        "source_url": "https://microdisign.ru/products/cat",
                        "products": [{"path": "item", "source_url": source}],
                    }
                ]
            }
            (root / "catalog_metadata.json").write_text(json.dumps(manifest))
            (folder / "metadata.json").write_text(
                json.dumps(
                    {
                        "title": "Детали",
                        "price": "420",
                        "Артикул": "МД 350001",
                        "images": [{"file": "one.jpg"}],
                    }
                )
            )
            (folder / "description.md").write_text(
                "# Детали\n\nОписание. Масштаб 1:350\n\nИсточник: original\n\n## Изображения"
            )
            Image.new("RGB", (50, 50), "white").save(folder / "one.jpg")
            with override_settings(MEDIA_ROOT=Path(media)):
                call_command("import_catalog", str(root), verbosity=0)
                p = Product.objects.get()
                self.assertEqual(p.scale, "1:350")
                self.assertFalse(p.available)
                self.assertTrue(Path(p.images.get().image.path).exists())
                p.title = "Изменено редактором"
                p.save()
                call_command("import_catalog", str(root), verbosity=0)
                p.refresh_from_db()
                self.assertEqual(p.title, "Изменено редактором")
                self.assertEqual(ProductImage.objects.count(), 1)


class CategoryTreeTests(TestCase):
    def setUp(self):
        self.root = Category.objects.create(name="Авиация", slug="air-root")
        self.child = Category.objects.create(name="Самолёты", slug="planes", parent=self.root)
        self.leaf = Category.objects.create(name="Масштаб 1:48", slug="planes-48", parent=self.child)
        self.other = Category.objects.create(name="Флот", slug="ships")
        Product.objects.create(category=self.leaf, title="Самолёт", slug="plane")
        Product.objects.create(category=self.other, title="Корабль", slug="ship")

    def test_navigation_and_parent_includes_descendants(self):
        response = self.client.get('/catalog/', {'category': 'air-root'})
        self.assertContains(response, 'Самолёт')
        self.assertNotContains(response, 'Корабль')
        categories = list(response.context['categories'])
        self.assertEqual([(c.name, c.depth, c.count) for c in categories[:3]], [
            ('Авиация', 0, 1), ('Самолёты', 1, 1), ('Масштаб 1:48', 2, 1),
        ])
        self.assertEqual(self.client.get('/catalog/', {'category': 'planes'}).context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get('/catalog/', {'category': 'missing'}).context['page_obj'].paginator.count, 0)

    def test_cycle_rejected_in_admin_form(self):
        from django.contrib.admin.sites import AdminSite
        from .admin import CategoryAdmin
        form_class = CategoryAdmin(Category, AdminSite()).get_form(None, self.root)
        form = form_class(data={'name': self.root.name, 'slug': self.root.slug, 'position': 0, 'parent': self.leaf.pk}, instance=self.root)
        self.assertFalse(form.is_valid())
        self.assertIn('parent', form.errors)


class NewsAndBannerTests(TestCase):
    def setUp(self):
        from .models import News, Banner
        self.news = News.objects.create(title='Новая модель', slug='новая-модель', body='Текст новости', published=True)
        self.draft = News.objects.create(title='Черновик', slug='draft', body='Текст', published=False)
        self.future = News.objects.create(title='Будущая', slug='future', body='Текст', published=True, published_at=timezone.now() + timezone.timedelta(days=1))
        self.banner = Banner.objects.create(title='Новости модели', image='banners/test.jpg', news=self.news, overlay_text='Новинка', show_grid=False)

    def test_published_news_and_drafts(self):
        listing = self.client.get('/news/')
        self.assertContains(listing, self.news.title)
        self.assertNotContains(listing, self.draft.title)
        self.assertNotContains(listing, self.future.title)
        self.assertEqual(self.client.get(self.news.get_absolute_url()).status_code, 200)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)
        self.assertEqual(self.client.get(self.future.get_absolute_url()).status_code, 404)

    def test_banner_on_home_and_publication_controls(self):
        response = self.client.get('/')
        self.assertContains(response, 'Новости модели')
        self.assertContains(response, 'Новинка')
        self.assertContains(response, self.news.get_absolute_url())
        self.assertNotContains(response, 'class="drawing-grid"')
        self.news.published = False
        self.news.save()
        self.assertEqual(self.banner.target_url, '')
        self.banner.active = False
        self.banner.save()
        self.assertNotContains(self.client.get('/'), 'Новости модели')

    def test_banner_link_validation(self):
        from django.core.exceptions import ValidationError
        from .models import Banner
        for url in ['javascript:alert(1)', '//evil.example', '/\\\\evil.example']:
            banner = Banner(title='Тест', image='banners/test.jpg', link_url=url)
            with self.assertRaises(ValidationError):
                banner.full_clean()
        for url in ['/news/', 'https://example.com/path']:
            Banner(title='Тест', image='banners/test.jpg', link_url=url).full_clean()
        self.banner.link_url = '/news/'
        with self.assertRaises(ValidationError):
            self.banner.full_clean()


class BannerAdminSourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from .models import News
        cls.admin = get_user_model().objects.create_superuser(username='editor', password='test-password')
        cls.cat = Category.objects.create(name='Категория', slug='category-admin')
        cls.product = Product.objects.create(category=cls.cat, title='Товар', slug='admin-product')
        cls.other = Product.objects.create(category=cls.cat, title='Другой', slug='other-product')
        cls.photo = ProductImage.objects.create(product=cls.product, image='products/test.webp')
        cls.other_photo = ProductImage.objects.create(product=cls.other, image='products/other.webp')
        cls.news = News.objects.create(title='Новость', slug='news-admin', body='Текст', image='news/test.webp')

    def setUp(self):
        self.client.force_login(self.admin)

    def data(self, **changes):
        data = {'title': 'Баннер', 'subtitle': '', 'label': '', 'overlay_text': '', 'image_alt': '', 'show_grid': 'on', 'position': '0', 'active': 'on', 'product': '', 'news': '', 'link_url': '', 'product_image_id': '', 'news_image_id': '', '_save': 'Сохранить'}
        data.update(changes)
        return data

    def test_select_product_image_and_reject_another_products_image(self):
        from .models import Banner
        invalid = self.client.post('/admin/shop/banner/add/', self.data(product=self.product.pk, product_image_id=self.other_photo.pk))
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(Banner.objects.filter(title='Баннер').exists())
        response = self.client.post('/admin/shop/banner/add/', self.data(product=self.product.pk, product_image_id=self.photo.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Banner.objects.get(title='Баннер').image.name, self.photo.image.name)

    def test_select_news_image_and_permissions(self):
        from .models import Banner
        response = self.client.post('/admin/shop/banner/add/', self.data(news=self.news.pk, news_image_id=self.news.pk))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Banner.objects.get(title='Баннер').image.name, self.news.image.name)
        response = self.client.get('/admin/shop/banner/source/', {'type': 'product', 'id': self.product.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['images'][0]['id'], self.photo.pk)
        self.client.logout()
        self.assertEqual(self.client.get('/admin/shop/banner/source/', {'type': 'product', 'id': self.product.pk}).status_code, 302)
