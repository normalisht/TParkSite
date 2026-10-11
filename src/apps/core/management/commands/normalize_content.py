from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, CategoryGroup, Service
from apps.content.models import Event, GalleryPhoto, Review
from apps.core.content_fixes import (
    describe_change,
    fix_caption,
    fix_name,
    fix_price,
    fix_text,
    fix_unit,
    has_unbalanced_quotes,
)
from apps.core.models import InfoPage, SiteSettings

SITE_TEXT_FIELDS = ("home_intro", "events_intro", "about_text", "nearby_text", "contacts_text", "founder_text")

FIELDS = {
    Service: {
        "name": fix_name,
        "short_description": fix_text,
        "description": fix_text,
        "price": fix_price,
        "price_unit": fix_unit,
    },
    Category: {"name": fix_name, "description": fix_text},
    CategoryGroup: {"name": fix_name},
    Event: {"title": fix_name, "description": fix_text, "price": fix_text},
    InfoPage: {"title": fix_name, "body": fix_text},
    Review: {"text": fix_text},
    GalleryPhoto: {"caption": fix_caption},
    SiteSettings: dict.fromkeys(SITE_TEXT_FIELDS, fix_text),
}


class Command(BaseCommand):
    help = (
        "Приводит контент к единому виду: «Т-Парк», «₽», единицы цен, кавычки, известные опечатки. "
        "Без --apply только показывает правки. Запускать после финального импорта старой базы."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Сохранить правки в базу")

    def handle(self, *args, apply, **options):
        changed = 0
        with transaction.atomic():
            for model, fields in FIELDS.items():
                label = model._meta.verbose_name
                has_updated_at = any(f.name == "updated_at" for f in model._meta.fields)
                for obj in model.objects.order_by("pk"):
                    updates = {}
                    for field, fix in fields.items():
                        old = getattr(obj, field) or ""
                        new = fix(old)
                        if new != old:
                            updates[field] = new
                            self.stdout.write(f"{label} #{obj.pk} {field}: {describe_change(old, new)}")
                        if fix is fix_name and has_unbalanced_quotes(new):
                            self.stdout.write(
                                self.style.WARNING(
                                    f"{label} #{obj.pk} {field}: непарные кавычки, поправьте вручную: {new}"
                                )
                            )
                    if not updates:
                        continue
                    changed += 1
                    if apply:
                        if has_updated_at:
                            updates["updated_at"] = timezone.now()  # lastmod в sitemap
                        model.objects.filter(pk=obj.pk).update(**updates)
        verdict = "Сохранено" if apply else "Найдено правок (без --apply ничего не сохранено)"
        self.stdout.write(self.style.SUCCESS(f"{verdict}: {changed} записей"))
