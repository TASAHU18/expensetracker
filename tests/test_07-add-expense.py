"""
Tests for Step 7: Add Expense (GET/POST /expenses/add).

Spec: .claude/specs/07-add-expense.md

These tests are written strictly against what the spec's Routes, Rules for
implementation, and Definition of Done sections say the feature should do —
not against the `add_expense` view's implementation in app.py.

Fixtures (`app`, `client`, `db_path`, `seeded`, `login`, `insert_expense`)
come from tests/conftest.py, which redirects database/db.py's DB_PATH to a
fresh temp file per test so each test is fully isolated. Because every test
function gets its own empty database, fixed/reused email addresses across
different test functions are safe.
"""

from datetime import date

import pytest

import database.db as db

ADD_EXPENSE_URL = "/expenses/add"

BASE_VALID_FORM = {
    "amount": "42.50",
    "category": "Food",
    "date": "2026-08-15",
    "description": "Groceries run",
}

# Generic vocabulary an inline validation message is likely to use. We don't
# assert exact wording (that's an implementation detail the spec doesn't
# pin down) — only that *some* error indication is rendered.
ERROR_PHRASES = (
    "error", "invalid", "required", "must", "enter a valid", "positive",
    "greater than", "select a valid",
)

PLACEHOLDER_STRINGS = ("N/A", "n/a", "None", "null", "-", "No description", "none")


def _new_user(db_path, email="add-expense-user@example.com", name="Add Expense User"):
    return db.create_user(name, email, "hash")


def _expense_count(user_id):
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["c"]
    finally:
        conn.close()


def _total_expense_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


def _latest_expense(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #

class TestAddExpenseAuthGuard:
    def test_get_while_logged_out_redirects_to_login(self, app, client):
        response = client.get(ADD_EXPENSE_URL)

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_post_while_logged_out_redirects_to_login_and_does_not_create_row(
        self, app, client, db_path
    ):
        before = _total_expense_count()

        response = client.post(ADD_EXPENSE_URL, data=BASE_VALID_FORM)

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

        after = _total_expense_count()
        assert after == before, (
            "An unauthenticated POST must not create an expense row"
        )


# --------------------------------------------------------------------- #
# GET while authenticated                                                #
# --------------------------------------------------------------------- #

class TestAddExpenseGet:
    def test_get_while_authenticated_returns_200_and_renders_form(
        self, app, client, seeded, login
    ):
        login(client, seeded["id"], seeded["name"])

        response = client.get(ADD_EXPENSE_URL)

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert 'name="amount"' in body, "Form should have an amount field"
        assert 'name="category"' in body, "Form should have a category field"
        assert 'name="date"' in body, "Form should have a date field"
        assert 'name="description"' in body, "Form should have a description field"

        for category in db.CATEGORIES:
            assert category in body, (
                f"Category select should be populated from database.db.CATEGORIES, "
                f"missing '{category}'"
            )

        assert date.today().strftime("%Y-%m-%d") in body, (
            "The date field should default to today's date"
        )


# --------------------------------------------------------------------- #
# Happy path                                                             #
# --------------------------------------------------------------------- #

class TestAddExpenseHappyPath:
    def test_valid_submission_creates_row_for_current_user_and_redirects_to_profile(
        self, app, client, db_path, login
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")

        response = client.post(ADD_EXPENSE_URL, data={
            "amount": "42.50",
            "category": "Food",
            "date": "2026-08-15",
            "description": "Groceries run",
        })

        assert response.status_code == 302
        assert response.headers["Location"] == "/profile", (
            "On success the app should redirect to /profile, not back to /expenses/add"
        )

        row = _latest_expense(user_id)
        assert row is not None, "A new expense row should have been created"
        assert row["user_id"] == user_id
        assert row["amount"] == 42.50
        assert row["category"] == "Food"
        assert row["date"] == "2026-08-15"
        assert row["description"] == "Groceries run"

    def test_valid_submission_appears_on_profile_and_updates_summary_stats(
        self, app, client, db_path, login
    ):
        user_id = _new_user(db_path, email="redirect-user@example.com", name="Redirect User")
        login(client, user_id, "Redirect User")

        response = client.post(
            ADD_EXPENSE_URL,
            data={
                "amount": "99.99",
                "category": "Entertainment",
                "date": "2026-08-10",
                "description": "Concert tickets",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Concert tickets" in body, (
            "The newly added expense should appear in the transaction list on /profile"
        )
        assert "₹99.99" in body, (
            "The summary stats on /profile should reflect the newly added expense"
        )


# --------------------------------------------------------------------- #
# Validation errors                                                      #
# --------------------------------------------------------------------- #

class TestAddExpenseValidation:
    @pytest.mark.parametrize("missing_field", ["amount", "category", "date"])
    def test_missing_required_field_rerenders_form_with_error_and_creates_no_row(
        self, app, client, db_path, login, missing_field
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = dict(BASE_VALID_FORM)
        form[missing_field] = ""

        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200, (
            "A validation failure should re-render the form, not redirect"
        )
        body = response.get_data(as_text=True)
        assert any(phrase in body.lower() for phrase in ERROR_PHRASES), (
            f"Expected a validation error message when '{missing_field}' is missing"
        )
        assert _expense_count(user_id) == before, (
            f"No row should be created when '{missing_field}' is missing"
        )

    def test_post_with_description_field_entirely_omitted_still_requires_others(
        self, app, client, db_path, login
    ):
        # description is optional, but omitting it shouldn't affect validation
        # of the required fields — sanity check the required-field rule still
        # fires correctly when description is absent from the payload at all.
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = {"amount": "", "category": "Food", "date": "2026-08-15"}
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        assert _expense_count(user_id) == before

    @pytest.mark.parametrize("bad_amount", ["abc", "twelve", "$50", "12,50", "NaN", "1e"])
    def test_non_numeric_amount_rerenders_form_with_error_and_creates_no_row(
        self, app, client, db_path, login, bad_amount
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = dict(BASE_VALID_FORM, amount=bad_amount)
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(phrase in body.lower() for phrase in ERROR_PHRASES), (
            f"Expected a validation error for non-numeric amount '{bad_amount}'"
        )
        assert _expense_count(user_id) == before, (
            f"No row should be created for non-numeric amount '{bad_amount}'"
        )

    @pytest.mark.parametrize("bad_amount", ["0", "0.00", "-1", "-42.50"])
    def test_zero_or_negative_amount_rerenders_form_with_error_and_creates_no_row(
        self, app, client, db_path, login, bad_amount
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = dict(BASE_VALID_FORM, amount=bad_amount)
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(phrase in body.lower() for phrase in ERROR_PHRASES), (
            f"Expected a validation error for non-positive amount '{bad_amount}'"
        )
        assert _expense_count(user_id) == before, (
            f"No row should be created for non-positive amount '{bad_amount}'"
        )

    @pytest.mark.parametrize(
        "bad_category", ["Groceries", "food", "Miscellaneous", "<script>alert(1)</script>"]
    )
    def test_category_not_in_fixed_list_rerenders_form_with_error_and_creates_no_row(
        self, app, client, db_path, login, bad_category
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = dict(BASE_VALID_FORM, category=bad_category)
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(phrase in body.lower() for phrase in ERROR_PHRASES), (
            f"Expected a validation error for category '{bad_category}' not in CATEGORIES"
        )
        assert _expense_count(user_id) == before, (
            f"No row should be created for out-of-list category '{bad_category}'"
        )

    @pytest.mark.parametrize(
        "bad_date",
        [
            "not-a-date",
            "2026-13-40",   # invalid month/day
            "08/17/2026",   # wrong format
            "2026/08/17",   # wrong separator
            "20260817",     # no separators
            "2026-02-30",   # matches YYYY-MM-DD shape but not a real calendar date
        ],
    )
    def test_invalid_or_malformed_date_rerenders_form_with_error_and_creates_no_row(
        self, app, client, db_path, login, bad_date
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")
        before = _expense_count(user_id)

        form = dict(BASE_VALID_FORM, date=bad_date)
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(phrase in body.lower() for phrase in ERROR_PHRASES), (
            f"Expected a validation error for malformed date '{bad_date}'"
        )
        assert _expense_count(user_id) == before, (
            f"No row should be created for malformed date '{bad_date}'"
        )

    def test_validation_failure_preserves_previously_entered_values(
        self, app, client, db_path, login
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")

        response = client.post(ADD_EXPENSE_URL, data={
            "amount": "-5",
            "category": "Health",
            "date": "2026-08-01",
            "description": "Doctor visit copay",
        })

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "-5" in body, (
            "Previously entered amount should be preserved in the re-rendered form"
        )
        assert "Doctor visit copay" in body, (
            "Previously entered description should be preserved in the re-rendered form"
        )
        assert "2026-08-01" in body, (
            "Previously entered date should be preserved in the re-rendered form"
        )


# --------------------------------------------------------------------- #
# Blank description                                                      #
# --------------------------------------------------------------------- #

class TestAddExpenseDescription:
    def test_blank_description_succeeds_and_stores_empty_or_none(
        self, app, client, db_path, login
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")

        response = client.post(ADD_EXPENSE_URL, data={
            "amount": "15.00",
            "category": "Other",
            "date": "2026-08-01",
            "description": "",
        })

        assert response.status_code == 302
        assert response.headers["Location"] == "/profile"

        row = _latest_expense(user_id)
        assert row is not None
        assert row["description"] in (None, ""), (
            "Blank description should be stored as empty/None, not a placeholder string"
        )
        assert row["description"] not in PLACEHOLDER_STRINGS, (
            "Blank description must not be replaced with a placeholder string"
        )

    def test_description_omitted_entirely_still_succeeds(self, app, client, db_path, login):
        user_id = _new_user(db_path)
        login(client, user_id, "Add Expense User")

        form = {"amount": "15.00", "category": "Other", "date": "2026-08-01"}
        response = client.post(ADD_EXPENSE_URL, data=form)

        assert response.status_code == 302
        assert response.headers["Location"] == "/profile"

        row = _latest_expense(user_id)
        assert row is not None
        assert row["description"] in (None, "")


# --------------------------------------------------------------------- #
# Profile entry point (Definition of Done)                               #
# --------------------------------------------------------------------- #

class TestProfileAddExpenseEntryPoint:
    def test_profile_page_links_to_add_expense_form(self, app, client, seeded, login):
        login(client, seeded["id"], seeded["name"])

        response = client.get("/profile")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert ADD_EXPENSE_URL in body, (
            "profile.html should contain a working link/button to /expenses/add"
        )
