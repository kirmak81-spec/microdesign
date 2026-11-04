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
