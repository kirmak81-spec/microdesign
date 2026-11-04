from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.management.base import BaseCommand
from shop.models import Page


class Command(BaseCommand):
    help = "Import saved source static pages; preserve admin edits on subsequent runs"

    def handle(self, *args, **options):
        for slug, title in [
            ("cash", "Оплата и доставка"),
            ("contacts", "Контакты и реквизиты"),
            ("company", "О производстве"),
        ]:
            source = settings.BASE_DIR / "docs" / f"source-{slug}.html"
            soup = BeautifulSoup(source.read_text(), "html.parser")
            block = soup.select_one(".block-id-main .textcontent")
            if not block:
                raise ValueError(f"Content block missing: {source}")
            for br in block.find_all("br"):
                br.replace_with("\n")
            paragraphs = []
            for node in block.find_all(["p", "li"]):
                text = node.get_text(" ", strip=True).replace("\xa0", " ")
                if text:
                    paragraphs.append(text)
            body = "\n\n".join(paragraphs)
            Page.objects.get_or_create(
                slug=slug,
                defaults={
                    "title": title,
                    "body": body,
                    "source_url": "https://microdisign.ru/" + slug,
                },
            )
            self.stdout.write(f"✓ {title}")
            if slug == "contacts":
                offer = next(
                    (a for a in block.find_all("a") if "оферт" in a.get_text().lower()),
                    None,
                )
                if offer:
                    url = urljoin("https://microdisign.ru", offer["href"])
                    Page.objects.get_or_create(
                        slug="offer",
                        defaults={
                            "title": "Договор оферты",
                            "body": "Исходный договор оферты ТПО «Микродизайн»:\n\n"
                            + url,
                            "source_url": "https://microdisign.ru/contacts",
                        },
                    )
        Page.objects.get_or_create(
            slug="privacy",
            defaults={
                "title": "Обработка персональных данных",
                "body": "Исходный сайт ссылается на политику конфиденциальности, но отдельный документ не найден на перенесённых страницах. До запуска магазина владелец должен предоставить актуальную политику обработки персональных данных. Приём платежей отключён. По вопросам данных: order@microdisign.ru.",
            },
        )
