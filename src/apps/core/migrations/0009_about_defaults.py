from django.db import migrations

from apps.core.about_defaults import fill_about_defaults


def forwards(apps, schema_editor):
    site = apps.get_model("core", "SiteSettings").objects.filter(pk=1).first()
    if site is not None:
        fill_about_defaults(site, apps.get_model("core", "ParkFormat"), apps.get_model("core", "FounderFact"))


class Migration(migrations.Migration):
    dependencies = [("core", "0008_about_page")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
