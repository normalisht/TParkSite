import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Консистентный снимок SQLite без остановки сайта (sqlite3 backup API)."

    def add_arguments(self, parser):
        parser.add_argument("destination", type=Path)

    def handle(self, *args, destination: Path, **options):
        destination.parent.mkdir(parents=True, exist_ok=True)
        connection.ensure_connection()
        target = sqlite3.connect(destination)
        try:
            connection.connection.backup(target)
        finally:
            target.close()
        self.stdout.write(self.style.SUCCESS(f"Снимок базы сохранён: {destination}"))
