import sqlite3
from pathlib import Path


class LegacyDB:
    """Старая SQLite Flask-версии, открытая только на чтение."""

    def __init__(self, path: Path):
        if not path.is_file():
            raise FileNotFoundError(f"Старая база не найдена: {path}")
        self.conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def rows(self, table: str, order_by: str = "id") -> list[dict]:
        cursor = self.conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')
        return [dict(row) for row in cursor]

    def close(self) -> None:
        self.conn.close()
