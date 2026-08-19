"""
Tests for Step 8: Edit Expense (GET/POST /expenses/<id>/edit).

Spec: .claude/specs/08-edit-expense.md

These tests are written strictly against what the spec's Routes, Rules for
implementation, and Definition of Done sections say the feature should do —
not against the `edit_expense` view's implementation in app.py.

Fixtures (`app`, `client`, `db_path`, `seeded`, `login`, `insert_expense`)
come from tests/conftest.py, which redirects database/db.py's DB_PATH to a
fresh temp file per test so each test is fully isolated. Because every test
function gets its own empty database, fixed/reused email addresses across
different test functions are safe.

`insert_expense` now returns the inserted row's id (cursor.lastrowid) so
tests here can build `/expenses/<id>/edit` URLs against a known row.
"""


import pytest

from database import db

# Generic vocabulary an inline validation message is likely to use. We don't
# assert exact wording (that's an implementation detail the spec doesn't
# pin down) — only that *some* error indication is rendered.
ERROR_PHRASES = (
    "error",
    "invalid",
    "required",
    "must",
    "enter a valid",
    "positive",
    "greater than",
    "select a valid",
)

BASE_VALID_FORM = {
    "amount": "42.50",
    "category": "Food",
    "date": "2026-08-15",
    "description": "Groceries run",
}


def _edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def _new_user(db_path, email="edit-expense-user@example.com", name="Edit Expense User"):
    return db.create_user(name, email, "hash")


def _expense_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #


class TestEditExpenseAuthGuard:
    def test_get_while_logged_out_redirects_to_login(
        self, app, client, db_path, insert_expense
    ):
        user_id = _new_user(db_path)
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        response = client.get(_edit_url(expense_id))

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_post_while_logged_out_redirects_to_login_and_does_not_mutate_row(
        self, app, client, db_path, insert_expense
    ):
        user_id = _new_user(db_path)
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")
        before = _expense_row(expense_id)

        response = client.post(_edit_url(expense_id), data=BASE_VALID_FORM)

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

        after = _expense_row(expense_id)
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]
        assert (
            after["description"] == before["description"]
        ), "An unauthenticated POST must not mutate the expense row"


# --------------------------------------------------------------------- #
# GET while authenticated — pre-filled form                             #
# --------------------------------------------------------------------- #


class TestEditExpenseGet:
    def test_get_own_expense_returns_200_and_prefills_form_values(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(
            user_id, "Transport", 15.75, "2026-08-05", "Taxi ride"
        )

        response = client.get(_edit_url(expense_id))

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert 'name="amount"' in body, "Form should have an amount field"
        assert 'name="category"' in body, "Form should have a category field"
        assert 'name="date"' in body, "Form should have a date field"
        assert 'name="description"' in body, "Form should have a description field"

        assert (
            "15.75" in body
        ), "Amount field should be pre-filled with the current value"
        assert (
            "Transport" in body
        ), "Category should be pre-filled with the current value"
        assert (
            "2026-08-05" in body
        ), "Date field should be pre-filled with the current value"
        assert (
            "Taxi ride" in body
        ), "Description field should be pre-filled with the current value"

        for category in db.CATEGORIES:
            assert category in body, (
                f"Category select should be populated from database.db.CATEGORIES, "
                f"missing '{category}'"
            )


# --------------------------------------------------------------------- #
# Happy path — POST                                                      #
# --------------------------------------------------------------------- #


class TestEditExpenseHappyPath:
    def test_valid_submission_updates_row_and_redirects_to_profile(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(
            user_id, "Food", 20.00, "2026-08-01", "Old description"
        )

        response = client.post(
            _edit_url(expense_id),
            data={
                "amount": "88.88",
                "category": "Shopping",
                "date": "2026-08-20",
                "description": "New description",
            },
        )

        assert response.status_code == 302
        assert (
            response.headers["Location"] == "/profile"
        ), "On success the app should redirect to /profile, not back to the edit form"

        row = _expense_row(expense_id)
        assert row is not None, "The expense row should still exist after the update"
        assert row["user_id"] == user_id, "Ownership must not change on edit"
        assert row["amount"] == 88.88
        assert row["category"] == "Shopping"
        assert row["date"] == "2026-08-20"
        assert row["description"] == "New description"

    def test_valid_submission_reflected_on_profile_page(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(
            db_path, email="reflect-user@example.com", name="Reflect User"
        )
        login(client, user_id, "Reflect User")
        expense_id = insert_expense(
            user_id, "Food", 20.00, "2026-08-01", "Old description"
        )

        response = client.post(
            _edit_url(expense_id),
            data={
                "amount": "77.00",
                "category": "Entertainment",
                "date": "2026-08-12",
                "description": "Updated concert tickets",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert (
            "Updated concert tickets" in body
        ), "The updated expense should appear in the transaction list on /profile"
        assert (
            "₹77.00" in body or "77.00" in body
        ), "The updated amount should be reflected on /profile"
        assert (
            "Old description" not in body
        ), "The stale description should no longer appear on /profile"

    def test_valid_submission_does_not_create_a_new_row(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(
            user_id, "Food", 20.00, "2026-08-01", "Old description"
        )

        conn = db.get_db()
        before_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()[
            "c"
        ]
        conn.close()

        client.post(_edit_url(expense_id), data=BASE_VALID_FORM)

        conn = db.get_db()
        after_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        conn.close()

        assert (
            after_count == before_count
        ), "Editing must update the existing row, not insert a new one"


# --------------------------------------------------------------------- #
# Validation errors                                                      #
# --------------------------------------------------------------------- #


class TestEditExpenseValidation:
    @pytest.mark.parametrize("missing_field", ["amount", "category", "date"])
    def test_missing_required_field_rerenders_form_with_error_and_leaves_row_unchanged(
        self, app, client, db_path, login, insert_expense, missing_field
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")
        before = _expense_row(expense_id)

        form = dict(BASE_VALID_FORM)
        form[missing_field] = ""

        response = client.post(_edit_url(expense_id), data=form)

        assert (
            response.status_code == 200
        ), "A validation failure should re-render the form, not redirect"
        body = response.get_data(as_text=True)
        assert any(
            phrase in body.lower() for phrase in ERROR_PHRASES
        ), f"Expected a validation error message when '{missing_field}' is missing"

        after = _expense_row(expense_id)
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]
        assert (
            after["description"] == before["description"]
        ), f"The row must remain unchanged when '{missing_field}' is missing"

    @pytest.mark.parametrize(
        "bad_amount", ["abc", "twelve", "$50", "12,50", "NaN", "1e"]
    )
    def test_non_numeric_amount_rerenders_form_with_error_and_leaves_row_unchanged(
        self, app, client, db_path, login, insert_expense, bad_amount
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")
        before = _expense_row(expense_id)

        form = dict(BASE_VALID_FORM, amount=bad_amount)
        response = client.post(_edit_url(expense_id), data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(
            phrase in body.lower() for phrase in ERROR_PHRASES
        ), f"Expected a validation error for non-numeric amount '{bad_amount}'"

        after = _expense_row(expense_id)
        assert (
            after["amount"] == before["amount"]
        ), f"The row must remain unchanged for non-numeric amount '{bad_amount}'"

    @pytest.mark.parametrize("bad_amount", ["0", "0.00", "-1", "-42.50"])
    def test_zero_or_negative_amount_rerenders_form_with_error_and_leaves_row_unchanged(
        self, app, client, db_path, login, insert_expense, bad_amount
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")
        before = _expense_row(expense_id)

        form = dict(BASE_VALID_FORM, amount=bad_amount)
        response = client.post(_edit_url(expense_id), data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(
            phrase in body.lower() for phrase in ERROR_PHRASES
        ), f"Expected a validation error for non-positive amount '{bad_amount}'"

        after = _expense_row(expense_id)
        assert (
            after["amount"] == before["amount"]
        ), f"The row must remain unchanged for non-positive amount '{bad_amount}'"

    @pytest.mark.parametrize(
        "bad_category",
        ["Groceries", "food", "Miscellaneous", "<script>alert(1)</script>"],
    )
    def test_category_not_in_fixed_list_rerenders_form_with_error_and_leaves_row_unchanged(
        self, app, client, db_path, login, insert_expense, bad_category
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")
        before = _expense_row(expense_id)

        form = dict(BASE_VALID_FORM, category=bad_category)
        response = client.post(_edit_url(expense_id), data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(
            phrase in body.lower() for phrase in ERROR_PHRASES
        ), f"Expected a validation error for category '{bad_category}' not in CATEGORIES"

        after = _expense_row(expense_id)
        assert (
            after["category"] == before["category"]
        ), f"The row must remain unchanged for out-of-list category '{bad_category}'"

    @pytest.mark.parametrize(
        "bad_date",
        [
            "not-a-date",
            "2026-13-40",  # invalid month/day
            "08/17/2026",  # wrong format
            "2026/08/17",  # wrong separator
            "20260817",  # no separators
            "2026-02-30",  # matches YYYY-MM-DD shape but not a real calendar date
        ],
    )
    def test_invalid_or_malformed_date_rerenders_form_with_error_and_leaves_row_unchanged(
        self, app, client, db_path, login, insert_expense, bad_date
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")
        before = _expense_row(expense_id)

        form = dict(BASE_VALID_FORM, date=bad_date)
        response = client.post(_edit_url(expense_id), data=form)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert any(
            phrase in body.lower() for phrase in ERROR_PHRASES
        ), f"Expected a validation error for malformed date '{bad_date}'"

        after = _expense_row(expense_id)
        assert (
            after["date"] == before["date"]
        ), f"The row must remain unchanged for malformed date '{bad_date}'"

    def test_validation_failure_preserves_submitted_values_in_form(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Health", 10.00, "2026-08-02", "Pharmacy")

        response = client.post(
            _edit_url(expense_id),
            data={
                "amount": "-5",
                "category": "Health",
                "date": "2026-08-01",
                "description": "Doctor visit copay",
            },
        )

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "-5" in body, (
            "The just-submitted amount should be preserved in the re-rendered form, "
            "not silently reverted to the old stored value"
        )
        assert (
            "Doctor visit copay" in body
        ), "Previously entered description should be preserved in the re-rendered form"
        assert (
            "2026-08-01" in body
        ), "Previously entered date should be preserved in the re-rendered form"


# --------------------------------------------------------------------- #
# Ownership / security                                                   #
# --------------------------------------------------------------------- #


class TestEditExpenseOwnership:
    def test_get_nonexistent_id_returns_404(self, app, client, db_path, login):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")

        response = client.get(_edit_url(999999))

        assert response.status_code == 404

    def test_post_nonexistent_id_returns_404_and_creates_no_row(
        self, app, client, db_path, login
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")

        conn = db.get_db()
        before_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()[
            "c"
        ]
        conn.close()

        response = client.post(_edit_url(999999), data=BASE_VALID_FORM)

        assert response.status_code == 404

        conn = db.get_db()
        after_count = conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
        conn.close()
        assert (
            after_count == before_count
        ), "A POST to a nonexistent expense id must not create or mutate any row"

    def test_get_other_users_expense_returns_404(
        self, app, client, db_path, login, insert_expense
    ):
        owner_id = _new_user(db_path, email="owner@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker@example.com", name="Attacker")
        expense_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )

        login(client, attacker_id, "Attacker")
        response = client.get(_edit_url(expense_id))

        assert (
            response.status_code == 404
        ), "A non-owner must never be able to view another user's expense form"
        body = response.get_data(as_text=True)
        assert (
            "Owner's lunch" not in body
        ), "The 404 response must not leak the other user's expense data"

    def test_post_other_users_expense_returns_404_and_does_not_mutate_row(
        self, app, client, db_path, login, insert_expense
    ):
        owner_id = _new_user(db_path, email="owner2@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker2@example.com", name="Attacker")
        expense_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )
        before = _expense_row(expense_id)

        login(client, attacker_id, "Attacker")
        response = client.post(
            _edit_url(expense_id),
            data={
                "amount": "1.00",
                "category": "Other",
                "date": "2026-01-01",
                "description": "Hacked",
            },
        )

        assert (
            response.status_code == 404
        ), "A non-owner must never be able to update another user's expense"

        after = _expense_row(expense_id)
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]
        assert (
            after["description"] == before["description"]
        ), "A non-owner's POST must not mutate the other user's expense row"

    def test_nonexistent_id_and_other_users_id_return_indistinguishable_404s(
        self, app, client, db_path, login, insert_expense
    ):
        # Guards against a shape-revealing 404: e.g. only real-but-foreign ids
        # getting a plain Flask abort(404) page while unknown ids get a
        # custom "no such expense" message (or vice versa), which would let
        # an attacker distinguish "exists but not yours" from "doesn't exist"
        # by response shape alone.
        owner_id = _new_user(db_path, email="owner3@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker3@example.com", name="Attacker")
        real_other_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )

        login(client, attacker_id, "Attacker")

        response_foreign = client.get(_edit_url(real_other_id))
        response_missing = client.get(_edit_url(999999))

        assert response_foreign.status_code == response_missing.status_code == 404
        assert response_foreign.get_data() == response_missing.get_data(), (
            "A foreign expense id and a nonexistent id must render an "
            "identical 404 response body, so neither response shape "
            "confirms the id exists"
        )


# --------------------------------------------------------------------- #
# Profile entry point (Definition of Done)                               #
# --------------------------------------------------------------------- #


class TestProfileEditExpenseEntryPoint:
    def test_profile_page_links_to_edit_expense_url_for_each_row(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Edit Expense User")
        expense_id = insert_expense(user_id, "Food", 12.00, "2026-08-04", "Snack")

        response = client.get("/profile")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert _edit_url(expense_id) in body, (
            "profile.html should contain a working link/button to "
            f"/expenses/{expense_id}/edit for each transaction row"
        )
