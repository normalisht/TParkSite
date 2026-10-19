from django.db import migrations

# Копия Season.DEFAULT_DATES: миграция не должна зависеть от текущего кода модели.
DEFAULT_DATES = {"new_year": ("15.12", "14.01"), "winter": ("01.12", "28.02")}


def create_seasons(apps, schema_editor):
    SiteSettings = apps.get_model("core", "SiteSettings")
    Season = apps.get_model("core", "Season")
    site, _ = SiteSettings.objects.get_or_create(pk=1)
    for kind, (start, end) in DEFAULT_DATES.items():
        Season.objects.get_or_create(kind=kind, defaults={"settings": site, "start": start, "end": end})


class Migration(migrations.Migration):
    dependencies = [("core", "0022_season")]

    operations = [migrations.RunPython(create_seasons, migrations.RunPython.noop)]
