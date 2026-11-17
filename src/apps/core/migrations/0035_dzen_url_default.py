from django.db import migrations

DZEN_URL = "https://dzen.ru/id/6239a453a4a5213a78439da7"


def fill_dzen_url(apps, schema_editor):
    # Строки настроек может ещё не быть (новая установка, тесты) — тогда создавать нечего.
    apps.get_model("core", "SiteSettings").objects.filter(dzen_url="").update(dzen_url=DZEN_URL)


class Migration(migrations.Migration):
    dependencies = [("core", "0034_site_dzen_url")]

    operations = [migrations.RunPython(fill_dzen_url, migrations.RunPython.noop)]
