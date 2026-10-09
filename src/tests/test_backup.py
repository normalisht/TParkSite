import sqlite3

import pytest
from django.core.management import call_command

from apps.catalog.models import Category

pytestmark = pytest.mark.django_db(transaction=True)


def test_backup_db_creates_consistent_copy(tmp_path):
    Category.objects.create(name="Байдарки")
    target = tmp_path / "backup.sqlite3"
    call_command("backup_db", str(target))
    with sqlite3.connect(target) as conn:
        names = [row[0] for row in conn.execute("SELECT name FROM catalog_category")]
    assert names == ["Байдарки"]
