from django.db import migrations

from apps.core.seo_content import fill_default_og_image, refresh_seo_content


def forwards(apps, schema_editor):
    site_settings = apps.get_model("core", "SiteSettings")
    refresh_seo_content(
        site_settings,
        apps.get_model("catalog", "Category"),
        apps.get_model("catalog", "Service"),
        apps.get_model("content", "Event"),
        apps.get_model("core", "InfoPage"),
    )
    fill_default_og_image(site_settings)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_specialday"),
        ("catalog", "0010_category_deleted_at_categorygroup_deleted_at_and_more"),
        ("content", "0014_event_deleted_at_review_deleted_at"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
