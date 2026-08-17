import calendar
import os
import sqlite3
from datetime import date, datetime

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # off by default per-connection in SQLite
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        if row["count"] > 0:
            return

        # method pinned to pbkdf2: this venv's Python is built against LibreSSL,
        # which lacks hashlib.scrypt (werkzeug's default hash method)
        password_hash = generate_password_hash("demo123", method="pbkdf2:sha256")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = cursor.lastrowid

        today = date.today()
        days_in_month = calendar.monthrange(today.year, today.month)[1]

        # 8 expenses covering all 7 fixed categories (Food appears twice)
        sample_expenses = [
            ("Food", 24.50, "Lunch at cafe"),
            ("Transport", 15.00, "Bus fare"),
            ("Bills", 85.00, "Electricity bill"),
            ("Health", 40.00, "Pharmacy"),
            ("Entertainment", 30.00, "Movie tickets"),
            ("Shopping", 60.00, "New shoes"),
            ("Other", 12.00, "Miscellaneous"),
            ("Food", 18.75, "Groceries"),
        ]

        # Spread dates evenly across the month; clamp so short months (e.g. Feb) are safe
        step = max(days_in_month // len(sample_expenses), 1)
        for index, (category, amount, description) in enumerate(sample_expenses):
            day = min(1 + index * step, days_in_month)
            expense_date = f"{today.year:04d}-{today.month:02d}-{day:02d}"
            conn.execute(
                """INSERT INTO expenses (user_id, amount, category, date, description)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, amount, category, expense_date, description),
            )

        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
    finally:
        conn.close()


def create_user(name, email, password_hash):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_profile_user(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return None

    return {
        "name": row["name"],
        "email": row["email"],
        "initials": _derive_initials(row["name"]),
        "member_since": _format_member_since(row["created_at"]),
    }


def get_expense_totals(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count
               FROM expenses WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()

    return {"total_spent": round(row["total"], 2), "transaction_count": row["count"]}


def get_recent_transactions(user_id, limit=10):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT date, description, category, amount FROM expenses
               WHERE user_id = ? ORDER BY date DESC, created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    finally:
        conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "date": datetime.strptime(row["date"], "%Y-%m-%d").strftime("%b %d, %Y"),
            "description": row["description"] or "",
            "category": row["category"],
            "amount": round(row["amount"], 2),
        })
    return transactions


def get_category_breakdown(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            """SELECT category, COALESCE(SUM(amount), 0) AS total FROM expenses
               WHERE user_id = ? GROUP BY category ORDER BY total DESC""",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()

    grand_total = sum(row["total"] for row in rows)

    categories = []
    for row in rows:
        percent = round(row["total"] / grand_total * 100) if grand_total else 0
        width_n = min(100, max(0, round(percent / 5) * 5))
        categories.append({
            "name": row["category"],
            "amount": round(row["total"], 2),
            "percent": percent,
            "width_class": f"profile-bar-w-{width_n}",
        })
    return categories


# ---- formatting helpers (no DB access) ----

def _derive_initials(name):
    parts = name.strip().split()
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _format_member_since(created_at):
    return datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
