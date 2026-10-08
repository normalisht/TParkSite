import sqlite3
from pathlib import Path

import pytest
from PIL import Image

from apps.core.legacy.runner import run_import

SCHEMA = Path(__file__).parent / "schema.sql"


class LegacyFixture:
    def __init__(self, tmp_path: Path):
        self.db_path = tmp_path / "legacy.db"
        self.images = tmp_path / "images"
        self.images.mkdir()
        self.conn = sqlite3.connect(self.db_path)
        self.conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    def insert(self, table: str, **values) -> None:
        columns = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        self.conn.execute(f'INSERT INTO "{table}" ({columns}) VALUES ({marks})', list(values.values()))
        self.conn.commit()

    def image(self, relpath: str, size=(40, 30)) -> Path:
        path = self.images / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", size, "orange").save(path, "JPEG")
        return path

    def run(self, **kwargs):
        return run_import(self.db_path, self.images, **kwargs)


@pytest.fixture
def legacy(tmp_path):
    fixture = LegacyFixture(tmp_path)
    yield fixture
    fixture.conn.close()
