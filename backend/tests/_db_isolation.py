"""Isolated temporary SQLite and storage configuration for automated tests.

Import and call ``configure_isolated_test_db()`` before importing ``app.database``
or ``app.main`` so every test run uses a fresh, writable, isolated SQLite file
and never touches the project's personal or demo database regardless of
``unittest`` discovery order.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _TESTS_DIR.parent
_PROJECT_ROOT = _BACKEND_DIR.parent
for _path in (str(_PROJECT_ROOT), str(_BACKEND_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

_ENV_ROOT_KEY = "_LATIRA_TEST_ISOLATED_ROOT"


def _cleanup_isolated_dir(root_path: str) -> None:
    shutil.rmtree(root_path, ignore_errors=True)


def configure_isolated_test_db() -> Path:
    """Ensure ``LATIRA_DB_PATH`` points to a run-scoped writable temp SQLite DB."""
    existing_root = os.environ.get(_ENV_ROOT_KEY)
    if existing_root and Path(existing_root).exists():
        return Path(os.environ["LATIRA_DB_PATH"])

    temp_root = Path(tempfile.mkdtemp(prefix="latira_test_suite_"))
    os.environ[_ENV_ROOT_KEY] = str(temp_root)
    atexit.register(_cleanup_isolated_dir, str(temp_root))

    db_path = temp_root / "latira_test.sqlite3"
    pose_dir = temp_root / "pose"
    pose_history_db = pose_dir / "history.sqlite3"
    thermal_dir = temp_root / "thermography"

    os.environ["LATIRA_DB_PATH"] = str(db_path)
    os.environ["POSE_STORAGE_DIR"] = str(pose_dir)
    os.environ["POSE_HISTORY_DB"] = str(pose_history_db)
    os.environ["LATIRA_THERMAL_DIR"] = str(thermal_dir)

    if "app.database" in sys.modules:
        database_mod = sys.modules["app.database"]
        database_mod.DB = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if "app.main" in sys.modules:
            main_mod = sys.modules["app.main"]
            main_mod.DB = db_path
            main_mod.init()

    return db_path
