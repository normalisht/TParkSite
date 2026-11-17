from django.db import migrations


def rename_button(apps, schema_editor):
    apps.get_model("texts", "SiteText").objects.filter(key="gallery.dzen_channel", text="Канал на Дзене").update(
        text="Дзен", label="Кнопка «Дзен»"
    )


class Migration(migrations.Migration):
    dependencies = [("texts", "0007_video_promo")]
    operations = [migrations.RunPython(rename_button, migrations.RunPython.noop)]
