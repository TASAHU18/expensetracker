import os

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

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


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "March 2025",
    }

    stats = {
        "total_spent": 285.25,
        "transaction_count": 8,
        "top_category": "Bills",
    }

    transactions = [
        {"date": "Aug 14, 2026", "description": "Groceries", "category": "Food", "amount": 18.75},
        {"date": "Aug 12, 2026", "description": "New shoes", "category": "Shopping", "amount": 60.00},
        {"date": "Aug 10, 2026", "description": "Miscellaneous", "category": "Other", "amount": 12.00},
        {"date": "Aug 08, 2026", "description": "Movie tickets", "category": "Entertainment", "amount": 30.00},
        {"date": "Aug 06, 2026", "description": "Pharmacy", "category": "Health", "amount": 40.00},
        {"date": "Aug 04, 2026", "description": "Electricity bill", "category": "Bills", "amount": 85.00},
        {"date": "Aug 02, 2026", "description": "Bus fare", "category": "Transport", "amount": 15.00},
        {"date": "Jul 30, 2026", "description": "Lunch at cafe", "category": "Food", "amount": 24.50},
    ]

    categories = [
        {"name": "Bills", "amount": 85.00, "percent": 30, "width_class": "profile-bar-w-30"},
        {"name": "Shopping", "amount": 60.00, "percent": 21, "width_class": "profile-bar-w-20"},
        {"name": "Food", "amount": 43.25, "percent": 15, "width_class": "profile-bar-w-15"},
        {"name": "Health", "amount": 40.00, "percent": 14, "width_class": "profile-bar-w-15"},
        {"name": "Entertainment", "amount": 30.00, "percent": 11, "width_class": "profile-bar-w-10"},
        {"name": "Transport", "amount": 15.00, "percent": 5, "width_class": "profile-bar-w-5"},
        {"name": "Other", "amount": 12.00, "percent": 4, "width_class": "profile-bar-w-5"},
    ]

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
