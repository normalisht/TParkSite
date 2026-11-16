from django.db import migrations

from apps.texts.registry import sync_texts


def forwards(apps, schema_editor):
    site_text = apps.get_model("texts", "SiteText")
    # Заголовок общей полки обложек: на вкладке «Видео» вместо неё — полки по подборкам.
    site_text.objects.filter(key="gallery.collections_title").delete()
    sync_texts(site_text, apps.get_model("texts", "HistoricalSiteText"))


class Migration(migrations.Migration):
    dependencies = [
        ("texts", "0005_gallery_video"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
