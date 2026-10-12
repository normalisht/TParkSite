"""Создаёт недостающие миниатюры imagekit — замена `generateimages` для запуска контейнера.

`generateimages` тоже пропускает готовые файлы, но печатает строку на каждую миниатюру: при каждом старте
в `docker logs` уходили тысячи строк. Здесь — только ошибки (в stderr) и итог одной строкой.
"""

from django.core.management.base import BaseCommand
from imagekit.registry import cachefile_registry, generator_registry


class Command(BaseCommand):
    help = "Создаёт миниатюры, которых ещё нет (готовые не пережимает); выводит только ошибки и итог."

    def handle(self, *args, **options):
        total = created = failed = 0
        for generator_id in generator_registry.get_ids():
            for file in cachefile_registry.get(generator_id):
                if not file.name:
                    continue
                total += 1
                if file.storage.exists(file.name):
                    continue
                try:
                    file.generate()
                except Exception as err:  # noqa: BLE001 — битое фото не должно останавливать остальные
                    failed += 1
                    self.stderr.write(f"Не удалось создать {file.name}: {err}")
                else:
                    created += 1
        self.stdout.write(f"Миниатюры: создано {created}, ошибок {failed}, всего нужно {total}.")
