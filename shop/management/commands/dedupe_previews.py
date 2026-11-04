"""Remove verified thumbnail entries from galleries; keep source/media files."""

import json
from pathlib import Path
from datetime import datetime, timezone

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from shop.catalog_images import imported_names, preview_pairs
from shop.models import ProductImage


class Command(BaseCommand):
    help = "Find verified archived previews in galleries. Dry-run by default; --apply saves a backup then removes database entries only."

    def add_arguments(self, parser):
        parser.add_argument("directory", type=Path)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--report", type=Path)

    def handle(self, *args, **options):
        root = options["directory"].resolve()
        manifest = root / "catalog_metadata.json"
        if not manifest.is_file():
            raise CommandError("catalog_metadata.json not found")
        data = json.loads(manifest.read_text())
        rows = list(ProductImage.objects.select_related("product").order_by("pk"))
        by_source = {}
        for row in rows:
            by_source.setdefault(row.product.source_url, []).append(row)
        plan = []
        checked_pairs = 0
        for category in data["categories"]:
            for record in category["products"]:
                folder = (root / category["path"] / record["path"]).resolve()
                if not folder.is_relative_to(root):
                    raise CommandError("Unsafe catalog path")
                gallery = by_source.get(record["source_url"], [])
                if not gallery:
                    continue
                meta = json.loads((folder / "metadata.json").read_text())
                pairs = preview_pairs(meta["images"], folder)
                checked_pairs += len(pairs)
                for pair in pairs:
                    preview = meta["images"][pair["remove_index"]]
                    original = meta["images"][pair["keep_index"]]
                    preview_names = imported_names(
                        root, (folder / preview["file"]).resolve()
                    )
                    original_names = imported_names(
                        root, (folder / original["file"]).resolve()
                    )
                    keepers = [
                        row
                        for row in gallery
                        if row.image.name in original_names
                        and Path(row.image.path).is_file()
                    ]
                    if not keepers:
                        continue
                    keeper = keepers[0]
                    for row in gallery:
                        if row.image.name in preview_names:
                            plan.append(
                                {
                                    "remove_pk": row.pk,
                                    "keep_pk": keeper.pk,
                                    "product_id": row.product_id,
                                    "product": row.product.title,
                                    "remove_file": row.image.name,
                                    "keep_file": keeper.image.name,
                                    "preview_source": preview["file"],
                                    "original_source": original["file"],
                                    **pair,
                                }
                            )
        summary = {
            "mode": "apply" if options["apply"] else "dry-run",
            "images_before": len(rows),
            "verified_source_pairs": checked_pairs,
            "remove_count": len(plan),
            "products_affected": len({p["product_id"] for p in plan}),
            "plan": plan,
        }
        if options["report"]:
            report = options["report"]
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        if options["apply"] and plan:
            with transaction.atomic():
                locked = list(ProductImage.objects.select_for_update().order_by("pk"))
                fingerprint = lambda values: [
                    (r.pk, r.product_id, r.image.name, r.position, r.caption)
                    for r in values
                ]
                if fingerprint(locked) != fingerprint(rows):
                    raise CommandError("Galleries changed during audit. Run again.")
                backup = (
                    settings.BASE_DIR
                    / ".backups"
                    / (
                        "previews-"
                        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                    )
                )
                backup.mkdir(parents=True)
                (backup / "product_images.json").write_text(
                    serializers.serialize("json", locked, indent=2)
                )
                (backup / "plan.json").write_text(
                    json.dumps(summary, ensure_ascii=False, indent=2)
                )
                removed, _ = ProductImage.objects.filter(
                    pk__in=[p["remove_pk"] for p in plan]
                ).delete()
                if removed != len(plan):
                    raise CommandError("Unexpected deletion count; rolled back")
                self.stdout.write(f"Backup: {backup}")
        self.stdout.write(
            json.dumps(
                {k: v for k, v in summary.items() if k != "plan"}, ensure_ascii=False
            )
        )
        self.stdout.write("Source catalog and media files are unchanged.")
