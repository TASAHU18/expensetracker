import math
import os
from datetime import date, datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_totals,
    get_profile_user,
    get_recent_transactions,
    get_user_by_email,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # regenerated each run, so sessions don't survive a restart

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        return render_template("register.html", error="All fields are required.")

    if password != confirm_password:
        return render_template("register.html", error="Passwords do not match.")

    if get_user_by_email(email) is not None:
        return render_template(
            "register.html", error="An account with that email already exists."
        )

    password_hash = generate_password_hash(password, method="pbkdf2:sha256")
    new_user_id = create_user(name, email, password_hash)

    session["user_id"] = new_user_id
    session["user_name"] = name
    return redirect(url_for("landing"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("login.html", error="All fields are required.")

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/terms", methods=["GET"])
def terms():
    return render_template("terms.html")


@app.route("/privacy", methods=["GET"])
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    return redirect(url_for("landing"))


# ------------------------------------------------------------------ #
# Profile date filter                                                 #
# ------------------------------------------------------------------ #

PRESETS = {"month": 0, "3months": 2, "6months": 5}
PRESET_LABELS = [
    ("all", "All Time"),
    ("month", "This Month"),
    ("3months", "Last 3 Months"),
    ("6months", "Last 6 Months"),
]


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _months_ago_start(today, n):
    month = today.month - n
    year = today.year
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _format_display_date(value):
    return datetime.strptime(value, "%Y-%m-%d").strftime("%b %d, %Y") if value else ""


def _build_date_filter(args):
    today = date.today()
    range_param = args.get("range", "").strip().lower()
    selected_range = "all"

    start_date = end_date = None
    filter_error = None

    if range_param in PRESETS:
        start_date = _months_ago_start(today, PRESETS[range_param]).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")
        selected_range = range_param
    elif range_param != "all":
        raw_start = args.get("start_date", "")
        raw_end = args.get("end_date", "")

        if raw_start or raw_end:
            selected_range = "custom"

        if raw_start and raw_end:
            parsed_start = _parse_date(raw_start)
            parsed_end = _parse_date(raw_end)
            if parsed_start and parsed_end:
                if parsed_start > parsed_end:
                    filter_error = "Start date must be on or before end date."
                else:
                    start_date = parsed_start.strftime("%Y-%m-%d")
                    end_date = parsed_end.strftime("%Y-%m-%d")
            else:
                filter_error = "Enter valid dates in YYYY-MM-DD format."

    return {
        "active": bool(start_date and end_date),
        "start_date": start_date or "",
        "end_date": end_date or "",
        "start_display": _format_display_date(start_date),
        "end_display": _format_display_date(end_date),
        "error": filter_error,
        "selected_range": selected_range,
    }


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = get_profile_user(session["user_id"])
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    date_filter = _build_date_filter(request.args)
    start_date = date_filter["start_date"]
    end_date = date_filter["end_date"]

    totals = get_expense_totals(session["user_id"], start_date, end_date)
    transactions = get_recent_transactions(
        session["user_id"], limit=10, start_date=start_date, end_date=end_date
    )
    categories = get_category_breakdown(session["user_id"], start_date, end_date)

    stats = {
        "total_spent": totals["total_spent"],
        "transaction_count": totals["transaction_count"],
        "top_category": categories[0]["name"] if categories else "—",
    }

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_filter=date_filter,
        preset_labels=PRESET_LABELS,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


MAX_DESCRIPTION_LENGTH = 200


def _validate_expense_form(amount_raw, category, date_raw):
    if not amount_raw or not category or not date_raw:
        return None, None, "Amount, category, and date are required."

    try:
        amount = float(amount_raw)
        # float() happily parses "nan"/"inf" as valid numbers, but those
        # aren't valid amounts and would break the NOT NULL insert below.
        if not math.isfinite(amount):
            raise ValueError
    except ValueError:
        return None, None, "Enter a valid amount."

    if amount <= 0:
        return None, None, "Amount must be greater than zero."

    if category not in CATEGORIES:
        return None, None, "Select a valid category."

    expense_date = _parse_date(date_raw)
    if expense_date is None:
        return None, None, "Enter a valid date."

    return amount, expense_date, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        form_values = {
            "amount": "",
            "category": "",
            "date": date.today().strftime("%Y-%m-%d"),
            "description": "",
        }
        return render_template(
            "add_expense.html", categories=CATEGORIES, form_values=form_values
        )

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date_raw = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()[:MAX_DESCRIPTION_LENGTH]

    form_values = {
        "amount": amount_raw,
        "category": category,
        "date": date_raw,
        "description": description,
    }

    amount, expense_date, error = _validate_expense_form(amount_raw, category, date_raw)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            form_values=form_values,
            error=error,
        )

    create_expense(
        session["user_id"],
        amount,
        category,
        expense_date.strftime("%Y-%m-%d"),
        description or None,
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
