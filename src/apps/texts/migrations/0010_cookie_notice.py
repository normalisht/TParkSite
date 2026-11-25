from django.db import migrations

from apps.texts.registry import BY_KEY, sync_texts


def update_notice(apps, schema_editor):
    texts = apps.get_model("texts", "SiteText")
    history = apps.get_model("texts", "HistoricalSiteText")
    texts.objects.filter(
        key="common.cookie_text",
        text="Яндекс Метрика помогает нам оценивать посещаемость сайта.",
    ).update(text=BY_KEY["common.cookie_text"].default)
    sync_texts(texts, history)


class Migration(migrations.Migration):
    dependencies = [("texts", "0009_metrika_consent_text")]
    operations = [migrations.RunPython(update_notice, migrations.RunPython.noop)]
