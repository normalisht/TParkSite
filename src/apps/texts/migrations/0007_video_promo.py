from django.db import migrations

from apps.texts.registry import sync_texts


def forwards(apps, schema_editor):
    sync_texts(apps.get_model("texts", "SiteText"), apps.get_model("texts", "HistoricalSiteText"))


class Migration(migrations.Migration):
    dependencies = [
        ("texts", "0006_gallery_video_shelves"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
