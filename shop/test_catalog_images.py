import hashlib
import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image, ImageDraw

from .catalog_images import imported_names, preview_pairs
from .models import Category, Product, ProductImage


def fixture(root):
    folder = root / "category" / "product"
    folder.mkdir(parents=True)
    image = Image.new("RGB", (320, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 200, 130), fill="navy")
    draw.ellipse((120, 70, 300, 220), fill="gold")
    image.save(folder / "photo.jpg", quality=95)
    image.resize((80, 60), Image.Resampling.LANCZOS).save(
        folder / "photo_2.jpg", quality=90
    )
    records = [
        {
            "file": "photo.jpg",
            "source_url": "https://microdisign.ru/ssl/u/aa/id/-/photo.jpg",
        },
        {
            "file": "photo_2.jpg",
            "source_url": "https://microdisign.ru/ssl/u/pic/bb/id/-/photo.jpg",
        },
    ]
    source = "https://microdisign.ru/products/category/product"
    manifest = {
        "categories": [
            {
                "name": "Авиация 1:32",
                "path": "category",
                "source_url": "https://microdisign.ru/products/category",
                "products": [{"path": "product", "source_url": source}],
            }
        ]
    }
    (root / "catalog_metadata.json").write_text(json.dumps(manifest))
    (folder / "metadata.json").write_text(
        json.dumps({"title": "Модель", "price": "100", "images": records})
    )
    (folder / "description.md").write_text("# Модель\n\nОписание. 1:32")
    return folder, records, source


class PairTests(SimpleTestCase):
    def test_verified_preview_maps_to_original(self):
        with TemporaryDirectory() as temp:
            folder, records, _ = fixture(Path(temp))
            pairs = preview_pairs(records, folder)
            self.assertEqual(
                [(p["remove_index"], p["keep_index"]) for p in pairs], [(1, 0)]
            )

    def test_different_picture_with_same_name_is_not_removed(self):
        with TemporaryDirectory() as temp:
            folder, records, _ = fixture(Path(temp))
            Image.new("RGB", (80, 60), "red").save(folder / "photo_2.jpg")
            self.assertEqual(preview_pairs(records, folder), [])

    def test_preview_without_original_and_genuine_second_photo_are_kept(self):
        with TemporaryDirectory() as temp:
            folder, records, _ = fixture(Path(temp))
            self.assertEqual(preview_pairs(records[1:], folder), [])
            records[1]["source_url"] = (
                "https://microdisign.ru/ssl/u/pic/bb/id/-/different.jpg"
            )
            self.assertEqual(preview_pairs(records, folder), [])


class CleanupTests(TestCase):
    def test_dry_run_backup_apply_and_repeated_apply(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            folder, records, source = fixture(root)
            media = root / "media"
            media.mkdir()
            category = Category.objects.create(name="Раздел", slug="category")
            product = Product.objects.create(
                title="Модель", slug="model", category=category, source_url=source
            )
            saved = []
            for index, record in enumerate(records):
                relative = next(
                    n
                    for n in imported_names(root, folder / record["file"])
                    if n.endswith(".webp")
                )
                target = media / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"kept media bytes")
                saved.append(
                    ProductImage.objects.create(
                        product=product, image=relative, position=index
                    )
                )
            originals_before = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.iterdir()
            }
            with override_settings(BASE_DIR=root, MEDIA_ROOT=media):
                call_command("dedupe_previews", root, stdout=StringIO())
                self.assertEqual(ProductImage.objects.count(), 2)
                call_command("dedupe_previews", root, apply=True, stdout=StringIO())
                self.assertEqual(
                    list(ProductImage.objects.values_list("pk", flat=True)),
                    [saved[0].pk],
                )
                backups = list((root / ".backups").glob("*/product_images.json"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(len(json.loads(backups[0].read_text())), 2)
                call_command("dedupe_previews", root, apply=True, stdout=StringIO())
                self.assertEqual(ProductImage.objects.count(), 1)
                for row in saved:
                    self.assertTrue((media / row.image.name).exists())
            self.assertEqual(
                originals_before,
                {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in folder.iterdir()
                },
            )

    def test_import_does_not_reintroduce_previews(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            with override_settings(MEDIA_ROOT=root / "media"):
                call_command("import_catalog", root, stdout=StringIO())
                self.assertEqual(ProductImage.objects.count(), 1)
                call_command("import_catalog", root, refresh=True, stdout=StringIO())
                self.assertEqual(ProductImage.objects.count(), 1)

    def test_missing_imported_original_keeps_preview(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            folder, records, source = fixture(root)
            category = Category.objects.create(name="Раздел", slug="category")
            product = Product.objects.create(
                title="Модель", slug="model", category=category, source_url=source
            )
            relative = next(
                n
                for n in imported_names(root, folder / records[1]["file"])
                if n.endswith(".webp")
            )
            ProductImage.objects.create(product=product, image=relative)
            with override_settings(BASE_DIR=root, MEDIA_ROOT=root / "media"):
                call_command("dedupe_previews", root, apply=True, stdout=StringIO())
                self.assertEqual(ProductImage.objects.count(), 1)
