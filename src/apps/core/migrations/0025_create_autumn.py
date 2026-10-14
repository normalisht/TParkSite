from django.db import migrations

# Копия Season.DEFAULT_DATES для осени: миграция не должна зависеть от текущего кода модели.
AUTUMN_DATES = ("01.09", "31.10")


def create_autumn(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Season = apps.get_model("core", "Season")
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    start, end = AUTUMN_DATES
    Season.objects.get_or_create(kind="autumn", defaults={"settings": site, "start": start, "end": end})


class Migration(migrations.Migration):
    dependencies = [("core", "0024_announcement_autumn")]

    operations = [migrations.RunPython(create_autumn, migrations.RunPython.noop)]
