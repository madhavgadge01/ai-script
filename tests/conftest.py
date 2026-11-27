import pytest
from pathlib import Path
from config.settings import settings
from app.database.connection import init_db

@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """
    Guarantees every test runs against its own isolated temporary SQLite database.
    Never connects to or modifies storage/uninotes.db.
    """
    test_db = tmp_path / "test_isolated.db"
    test_exports = tmp_path / "test_exports"
    test_exports.mkdir(parents=True, exist_ok=True)

    # Monkeypatch settings so all components use test_db and test_exports
    monkeypatch.setattr(settings, "db_path", test_db)
    monkeypatch.setattr(settings, "exports_dir", test_exports)

    # Initialize isolated schema
    init_db(test_db)

    yield test_db
