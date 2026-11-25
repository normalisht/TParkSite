from django.db import migrations

COPY_UPDATES = {
    "common.cookie_text": (
        "С вашего согласия мы используем необязательные cookie, чтобы понять, как посетители пользуются сайтом, "
        "и сделать его удобнее. Веб-аналитика может записывать действия на страницах.",
        "Мы используем необязательные cookie и Яндекс Метрику, чтобы понять, как посетители пользуются сайтом, "
        "и сделать его удобнее. Если вы согласитесь, Метрика может записывать действия на страницах.",
    ),
    "common.cookie_allow": ("Разрешить cookie", "Принять"),
    "common.cookie_refuse": ("Отказаться", "Отклонить"),
}


def update_defaults(apps, schema_editor):
    texts = apps.get_model("texts", "SiteText")
    for key, (previous, current) in COPY_UPDATES.items():
        texts.objects.filter(key=key, text=previous).update(text=current)


class Migration(migrations.Migration):
    dependencies = [("texts", "0010_cookie_notice")]
    operations = [migrations.RunPython(update_defaults, migrations.RunPython.noop)]
