from django.db import migrations

from apps.core.about_defaults import strip_founder_heading


def forwards(apps, schema_editor):
    site = apps.get_model("core", "SiteSettings").objects.filter(pk=1).first()
    if site is None:
        return
    text = strip_founder_heading(site.founder_text, site.founder_name, site.founder_lead)
    if text != site.founder_text:
        site.founder_text = text
        site.save(update_fields=["founder_text"])


class Migration(migrations.Migration):
    dependencies = [("core", "0014_privacy_policy")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
