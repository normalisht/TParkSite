from django.db import migrations

# dzen_import — живой модуль: если в его Video(...) появится новое обязательное поле, на старой базе миграция упадёт —
# тогда заморозьте здесь копию логики.
from apps.content.dzen_import import import_channel, load_channel


def import_dzen_channel(apps, schema_editor):
    # Без услуг каталога — тесты или новая установка: в сеть не ходим, канал переносит команда import_dzen_channel.
    Service = apps.get_model("catalog", "Service")
    if not Service.objects.exists():
        return
    import_channel(
        Video=apps.get_model("content", "Video"),
        VideoCollection=apps.get_model("content", "VideoCollection"),
        VideoCollectionItem=apps.get_model("content", "VideoCollectionItem"),
        Service=Service,
        data=load_channel(),
        # migrate печатает «Applying …» без перевода строки и дописывает « OK» в конце.
        log=lambda line: print(f"\n  {line}", end=""),
    )


class Migration(migrations.Migration):
    # Обложки качаются с Дзена: без общей транзакции SQLite не заперт на время скачивания, а прерванный перенос
    # повторный migrate доделывает без дублей.
    atomic = False

    dependencies = [
        ("catalog", "0010_category_deleted_at_categorygroup_deleted_at_and_more"),
        ("content", "0017_video_dzen_url"),
    ]

    operations = [migrations.RunPython(import_dzen_channel, migrations.RunPython.noop)]
