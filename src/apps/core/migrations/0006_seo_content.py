from django.db import migrations

from apps.core.seo_content import fill_seo_content


def forwards(apps, schema_editor):
    fill_seo_content(apps.get_model("core", "SiteSettings"), apps.get_model("catalog", "Category"))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_seo"),
        ("catalog", "0003_seo"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
