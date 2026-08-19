import tempfile

import pytest

from database import db

db.DB_PATH = tempfile.mkstemp(suffix=".db")[1]

import app as app_module  # import deferred until DB_PATH is redirected


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setattr(db, "DB_PATH", path)
    db.init_db()
    return path


@pytest.fixture
def seeded(db_path):
    db.seed_db()
    return db.get_user_by_email("demo@spendly.com")


@pytest.fixture
def app(db_path):
    app_module.app.config.update(TESTING=True)
    return app_module.app


@pytest.fixture
def login():
    def _login(client, user_id, user_name="Demo User"):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["user_name"] = user_name

    return _login


@pytest.fixture
def insert_expense(db_path):
    def _insert(user_id, category, amount, date_str, description=None):
        conn = db.get_db()
        try:
            cursor = conn.execute(
                """INSERT INTO expenses (user_id, category, amount, date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, category, amount, date_str, description),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    return _insert
