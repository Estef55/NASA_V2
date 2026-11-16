from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB = Path(os.getenv('LATIRA_DB_PATH', PROJECT_ROOT / 'data' / 'database' / 'latira.sqlite3'))
DB.parent.mkdir(parents=True, exist_ok=True)

@contextmanager
def conn():
    """Yield a row-enabled SQLite connection and always commit/rollback/close."""
    connection = sqlite3.connect(DB, timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
