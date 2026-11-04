import hashlib, json, re, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from PIL import Image, ImageOps
from shop.models import Category, Product, ProductImage
from shop.catalog_images import preview_pairs


class Command(BaseCommand):
    help = "Import archived catalog once. Existing products and editor changes are preserved."

    def add_arguments(self, parser):
        parser.add_argument("directory", type=Path)
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Overwrite imported product fields and rebuild image relations explicitly",
        )
        parser.add_argument(
            "--originals",
            action="store_true",
            help="Copy original images instead of creating optimized WebP",
        )

    def handle(self, *args, **options):
        root = options["directory"].resolve()
        manifest = root / "catalog_metadata.json"
        if not manifest.exists():
            raise CommandError("catalog_metadata.json not found")
        data = json.loads(manifest.read_text())
        imported = skipped = missing = images = 0
        pool = ThreadPoolExecutor(max_workers=4)
        for pos, category in enumerate(data["categories"]):
            cat_slug = category["source_url"].rstrip("/").split("/")[-1]
            cat, _ = Category.objects.get_or_create(
                slug=cat_slug, defaults={"name": category["name"], "position": pos}
            )
            for record_pos, record in enumerate(category["products"]):
                folder = (root / category["path"] / record["path"]).resolve()
                if not folder.is_relative_to(root):
                    raise CommandError("Unsafe catalog path")
                source = record["source_url"]
                if (
                    Product.objects.filter(source_url=source).exists()
                    and not options["refresh"]
                ):
                    skipped += 1
                    continue
                meta = json.loads((folder / "metadata.json").read_text())
                description = (
                    (folder / "description.md").read_text().split("\n## Изображения")[0]
                )
                description = (
                    re.sub(r"^#.*\n", "", description).split("\nИсточник:")[0].strip()
                )
                match = re.search(
                    r"1\s*[:_]\s*(\d+)", description + " " + category["name"]
                )
                scale = "1:" + str(int(match[1])) if match else ""
                raw = (
                    str(meta.get("price", ""))
                    .replace(" ", "")
                    .replace("\xa0", "")
                    .replace(",", ".")
                )
                try:
                    price = Decimal(raw) if raw else None
                except InvalidOperation:
                    price = None
                slug = cat_slug + "-" + source.rstrip("/").split("/")[-1]
                if len(slug) > 240:
                    slug = (
                        slug[:220]
                        + "-"
                        + hashlib.sha256(source.encode()).hexdigest()[:12]
                    )

                def prepare_image(entry):
                    index, img = entry
                    original = (folder / img["file"]).resolve()
                    if not original.is_relative_to(root) or not original.is_file():
                        return None
                    identity = hashlib.sha256(
                        str(original.relative_to(root)).encode()
                    ).hexdigest()[:24]
                    ext = original.suffix.lower() if options["originals"] else ".webp"
                    relative = Path("imported") / identity[:2] / (identity + ext)
                    target = settings.MEDIA_ROOT / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not target.exists():
                        try:
                            if options["originals"]:
                                shutil.copyfile(original, target)
                            else:
                                with Image.open(original) as im:
                                    im.draft("RGB", (1600, 1600))
                                    im = ImageOps.exif_transpose(im)
                                    im.thumbnail((1600, 1600))
                                    im.convert("RGB").save(
                                        target, "WEBP", quality=82, method=0
                                    )
                        except Image.DecompressionBombError:
                            # Preserve oversized scans without decoding or allocating hundreds of MB.
                            relative = relative.with_suffix(original.suffix.lower())
                            target = settings.MEDIA_ROOT / relative
                            if not target.exists():
                                shutil.copyfile(original, target)
                            self.stderr.write(
                                f"Oversized scan preserved as original: {original.name}"
                            )
                        except (OSError, ValueError) as exc:
                            self.stderr.write(f"Image skipped: {original.name}: {exc}")
                            return None
                    return (str(relative), index)

                source_images = meta.get("images", [])
                previews = {
                    pair["remove_index"]
                    for pair in preview_pairs(source_images, folder)
                }
                prepared = list(
                    pool.map(
                        prepare_image,
                        (
                            (index, image)
                            for index, image in enumerate(source_images)
                            if index not in previews
                        ),
                    )
                )
                image_values = [entry for entry in prepared if entry is not None]
                missing += len(prepared) - len(image_values)
                with transaction.atomic():
                    item, _ = Product.objects.update_or_create(
                        source_url=source,
                        defaults={
                            "title": meta["title"],
                            "slug": slug,
                            "category": cat,
                            "sku": meta.get("Артикул", ""),
                            "description": description,
                            "price": price,
                            "scale": scale,
                            "manufacturer": meta.get("Производитель", ""),
                            "featured": pos == 0 and record_pos < 8,
                        },
                    )
                    item.images.all().delete()
                    ProductImage.objects.bulk_create(
                        [
                            ProductImage(
                                product=item, image=name, position=i, caption=item.title
                            )
                            for name, i in image_values
                        ]
                    )
                imported += 1
                images += len(image_values)
                if imported % 50 == 0:
                    self.stdout.write(
                        f"{imported} products / {images} images", ending="\n"
                    )
                    self.stdout.flush()
            self.stdout.write(f"✓ {cat.name}")
        pool.shutdown()
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported: {imported}; preserved: {skipped}; images: {images}; missing: {missing}"
            )
        )
