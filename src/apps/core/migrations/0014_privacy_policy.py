from django.db import migrations

from apps.core.privacy_defaults import ensure_privacy_page


def forwards(apps, schema_editor):
    ensure_privacy_page(apps.get_model("core", "InfoPage"), apps.get_model("core", "SiteSettings"))


class Migration(migrations.Migration):
    dependencies = [("core", "0013_vk_label")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
