from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.legacy.runner import LegacyImportError, run_import


class Command(BaseCommand):
    help = "Импорт данных из старой Flask-версии (SQLite + папка images)."

    def add_arguments(self, parser):
        parser.add_argument("--db", required=True, type=Path, help="Путь к старой T_Park.db")
        parser.add_argument("--images", required=True, type=Path, help="Путь к старой папке app/static/images")
        parser.add_argument("--flush", action="store_true", help="Удалить текущий контент перед импортом")
        parser.add_argument(
            "--price-csv", type=Path, default=Path("price_legacy.csv"), help="Куда выгрузить таблицу price"
        )

    def handle(self, *args, db, images, flush, price_csv, **options):
        try:
            report = run_import(db, images, flush=flush, price_csv=price_csv)
        except (LegacyImportError, FileNotFoundError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(report.render())
        self.stdout.write(self.style.SUCCESS("Импорт завершён."))
