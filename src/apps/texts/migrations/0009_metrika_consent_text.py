from django.db import migrations

OLD_TEXT = "Мы используем cookie и Яндекс Метрику, чтобы сайт работал удобнее."
NEW_TEXT = "Яндекс Метрика помогает нам оценивать посещаемость сайта."


def update_notice(apps, schema_editor):
    apps.get_model("texts", "SiteText").objects.filter(key="common.cookie_text", text=OLD_TEXT).update(text=NEW_TEXT)


def restore_notice(apps, schema_editor):
    apps.get_model("texts", "SiteText").objects.filter(key="common.cookie_text", text=NEW_TEXT).update(text=OLD_TEXT)


class Migration(migrations.Migration):
    dependencies = [("texts", "0008_dzen_button_label")]
    operations = [migrations.RunPython(update_notice, restore_notice)]
