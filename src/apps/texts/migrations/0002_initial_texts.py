from django.db import migrations

from apps.texts.registry import sync_texts


def forwards(apps, schema_editor):
    sync_texts(apps.get_model("texts", "SiteText"), apps.get_model("texts", "HistoricalSiteText"))


class Migration(migrations.Migration):
    dependencies = [("texts", "0001_initial")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
