from django.db import migrations, models

from apps.core.slugs import slugify_ru


def fill_slugs(apps, schema_editor):
    Event = apps.get_model("content", "Event")
    used = set()
    for event in Event.objects.order_by("date", "id"):
        base = slugify_ru(f"{event.title} {event.date:%Y}")
        slug, counter = base, 2
        while slug in used:
            slug = f"{base}-{counter}"
            counter += 1
        used.add(slug)
        event.slug = slug
        event.save(update_fields=["slug"])


class Migration(migrations.Migration):
    dependencies = [
        ("content", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="slug",
            field=models.SlugField(blank=True, max_length=255, verbose_name="Адрес страницы"),
        ),
        migrations.RunPython(fill_slugs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="event",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text="Пусто — из заголовка и года.",
                max_length=255,
                unique=True,
                verbose_name="Адрес страницы",
            ),
        ),
    ]
