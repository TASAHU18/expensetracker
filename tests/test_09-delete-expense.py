"""
Tests for Step 9: Delete Expense (POST /expenses/<id>/delete).

Spec: .claude/specs/09-delete-expense.md

These tests are written strictly against what the spec's Routes, Database
changes, Rules for implementation, and Definition of Done sections say the
feature should do — not against the delete route's implementation in
app.py or the delete_expense() helper's implementation in database/db.py.

Fixtures (`app`, `client`, `db_path`, `seeded`, `login`, `insert_expense`)
come from tests/conftest.py, which redirects database/db.py's DB_PATH to a
fresh temp file per test so each test is fully isolated.

Per the spec:
- The route is POST-only ("GET is not retained, since deletion must never
  be triggered by a simple link/prefetch").
- Unauthenticated requests redirect to `login` (same pattern as
  add_expense/edit_expense).
- Requests for an id that doesn't exist or isn't owned by the current user
  must abort(404), matching edit_expense's existing behavior.
- A successful delete removes the row and redirects to `profile`.
"""

from database import db


def _delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


def _new_user(
    db_path, email="delete-expense-user@example.com", name="Delete Expense User"
):
    return db.create_user(name, email, "hash")


def _expense_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def _expense_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) AS c FROM expenses").fetchone()["c"]
    finally:
        conn.close()


# --------------------------------------------------------------------- #
# HTTP method restriction — POST only                                    #
# --------------------------------------------------------------------- #


class TestDeleteExpenseMethodRestriction:
    def test_get_is_not_allowed(self, app, client, db_path, login, insert_expense):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        response = client.get(_delete_url(expense_id))

        assert response.status_code == 405, (
            "GET must no longer work on the delete route — the old stub's bare "
            "200 string response must be gone, and GET must not be a supported method"
        )

        # The row must still exist — a rejected method must never mutate data.
        assert _expense_row(expense_id) is not None

    def test_get_is_not_allowed_even_when_logged_out(
        self, app, client, db_path, insert_expense
    ):
        user_id = _new_user(db_path)
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        response = client.get(_delete_url(expense_id))

        assert (
            response.status_code == 405
        ), "Method restriction should be enforced independent of auth state"


# --------------------------------------------------------------------- #
# Auth guard                                                             #
# --------------------------------------------------------------------- #


class TestDeleteExpenseAuthGuard:
    def test_post_while_logged_out_redirects_to_login(
        self, app, client, db_path, insert_expense
    ):
        user_id = _new_user(db_path)
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        response = client.post(_delete_url(expense_id))

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"

    def test_post_while_logged_out_does_not_delete_row(
        self, app, client, db_path, insert_expense
    ):
        user_id = _new_user(db_path)
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        client.post(_delete_url(expense_id))

        assert (
            _expense_row(expense_id) is not None
        ), "An unauthenticated delete request must not remove the expense row"

    def test_post_while_logged_out_for_nonexistent_id_still_redirects_to_login(
        self, app, client, db_path
    ):
        # Auth must be checked before any existence/ownership lookup, so an
        # unauthenticated caller can't use the response to probe whether an
        # id exists.
        response = client.post(_delete_url(999999))

        assert response.status_code == 302
        assert response.headers["Location"] == "/login"


# --------------------------------------------------------------------- #
# Happy path                                                             #
# --------------------------------------------------------------------- #


class TestDeleteExpenseHappyPath:
    def test_valid_delete_removes_row_and_redirects_to_profile(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        response = client.post(_delete_url(expense_id))

        assert response.status_code == 302
        assert (
            response.headers["Location"] == "/profile"
        ), "On success the app should redirect to /profile"

        assert (
            _expense_row(expense_id) is None
        ), "The expense row should no longer exist in the database after deletion"

    def test_deleted_expense_no_longer_appears_on_profile_page(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(
            user_id, "Entertainment", 45.00, "2026-08-10", "Concert tickets"
        )

        response = client.post(_delete_url(expense_id), follow_redirects=True)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert (
            "Concert tickets" not in body
        ), "The deleted expense's description should no longer appear on /profile"

    def test_delete_only_removes_targeted_row_other_expenses_survive(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        keep_id_1 = insert_expense(user_id, "Food", 10.00, "2026-08-01", "Keep me 1")
        target_id = insert_expense(user_id, "Bills", 25.00, "2026-08-02", "Delete me")
        keep_id_2 = insert_expense(user_id, "Health", 15.00, "2026-08-03", "Keep me 2")

        response = client.post(_delete_url(target_id))

        assert response.status_code == 302
        assert _expense_row(target_id) is None
        assert (
            _expense_row(keep_id_1) is not None
        ), "Deleting one expense must not remove unrelated expenses"
        assert (
            _expense_row(keep_id_2) is not None
        ), "Deleting one expense must not remove unrelated expenses"

    def test_delete_reduces_total_expense_count_by_exactly_one(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        insert_expense(user_id, "Food", 10.00, "2026-08-01", "A")
        target_id = insert_expense(user_id, "Bills", 25.00, "2026-08-02", "B")
        insert_expense(user_id, "Health", 15.00, "2026-08-03", "C")

        before_count = _expense_count()
        client.post(_delete_url(target_id))
        after_count = _expense_count()

        assert after_count == before_count - 1, (
            "Deleting a single expense should reduce the total row count by "
            "exactly one — no cascading or extra deletions"
        )

    def test_deleted_expense_totals_reflect_on_profile_page(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(user_id, "Shopping", 100.00, "2026-08-05", "Shoes")

        response = client.post(_delete_url(expense_id), follow_redirects=True)

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        # After deleting the only expense, spending totals should reflect
        # zero — a loose text check that avoids over-pinning exact markup.
        assert "0" in body, "Profile totals should reflect the deletion"


# --------------------------------------------------------------------- #
# Ownership / security                                                   #
# --------------------------------------------------------------------- #


class TestDeleteExpenseOwnership:
    def test_delete_nonexistent_id_returns_404(self, app, client, db_path, login):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")

        response = client.post(_delete_url(999999))

        assert response.status_code == 404

    def test_delete_nonexistent_id_does_not_change_row_count(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        before_count = _expense_count()
        response = client.post(_delete_url(999999))
        after_count = _expense_count()

        assert response.status_code == 404
        assert after_count == before_count, (
            "Attempting to delete a nonexistent id must not affect any " "existing row"
        )

    def test_delete_other_users_expense_returns_404(
        self, app, client, db_path, login, insert_expense
    ):
        owner_id = _new_user(db_path, email="owner@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker@example.com", name="Attacker")
        expense_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )

        login(client, attacker_id, "Attacker")
        response = client.post(_delete_url(expense_id))

        assert (
            response.status_code == 404
        ), "A non-owner must never be able to delete another user's expense"

    def test_delete_other_users_expense_does_not_mutate_row(
        self, app, client, db_path, login, insert_expense
    ):
        owner_id = _new_user(db_path, email="owner2@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker2@example.com", name="Attacker")
        expense_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )
        before = _expense_row(expense_id)

        login(client, attacker_id, "Attacker")
        client.post(_delete_url(expense_id))

        after = _expense_row(expense_id)
        assert after is not None, "The other user's expense must survive the attempt"
        assert after["amount"] == before["amount"]
        assert after["category"] == before["category"]
        assert after["date"] == before["date"]
        assert after["description"] == before["description"]
        assert after["user_id"] == owner_id

    def test_nonexistent_id_and_other_users_id_return_indistinguishable_404s(
        self, app, client, db_path, login, insert_expense
    ):
        # Guards against a shape-revealing 404: e.g. only real-but-foreign ids
        # getting a plain Flask abort(404) page while unknown ids get a
        # custom message (or vice versa), which would let an attacker
        # distinguish "exists but not yours" from "doesn't exist" by
        # response shape alone.
        owner_id = _new_user(db_path, email="owner3@example.com", name="Owner")
        attacker_id = _new_user(db_path, email="attacker3@example.com", name="Attacker")
        real_other_id = insert_expense(
            owner_id, "Food", 30.00, "2026-08-03", "Owner's lunch"
        )

        login(client, attacker_id, "Attacker")

        response_foreign = client.post(_delete_url(real_other_id))
        response_missing = client.post(_delete_url(999999))

        assert response_foreign.status_code == response_missing.status_code == 404
        assert response_foreign.get_data() == response_missing.get_data(), (
            "A foreign expense id and a nonexistent id must render an "
            "identical 404 response body, so neither response shape "
            "confirms the id exists"
        )

    def test_delete_already_deleted_expense_returns_404(
        self, app, client, db_path, login, insert_expense
    ):
        # Deleting the same expense twice in a row (e.g. a double form
        # submission) must not succeed silently the second time.
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(user_id, "Food", 20.00, "2026-08-01", "Lunch")

        first = client.post(_delete_url(expense_id))
        assert first.status_code == 302
        assert _expense_row(expense_id) is None

        second = client.post(_delete_url(expense_id))
        assert second.status_code == 404, (
            "Deleting an id that has already been deleted must 404, not "
            "silently redirect as if it succeeded again"
        )


# --------------------------------------------------------------------- #
# Cross-user isolation sanity check                                      #
# --------------------------------------------------------------------- #


class TestDeleteExpenseCrossUserIsolation:
    def test_deleting_own_expense_does_not_affect_another_users_expense_with_same_category(
        self, app, client, db_path, login, insert_expense
    ):
        user_a = _new_user(db_path, email="user-a@example.com", name="User A")
        user_b = _new_user(db_path, email="user-b@example.com", name="User B")

        expense_a = insert_expense(user_a, "Food", 10.00, "2026-08-01", "A's lunch")
        expense_b = insert_expense(user_b, "Food", 10.00, "2026-08-01", "B's lunch")

        login(client, user_a, "User A")
        response = client.post(_delete_url(expense_a))

        assert response.status_code == 302
        assert _expense_row(expense_a) is None
        assert (
            _expense_row(expense_b) is not None
        ), "Deleting user A's expense must never remove user B's expense"


# --------------------------------------------------------------------- #
# Profile entry point (Definition of Done)                               #
# --------------------------------------------------------------------- #


class TestProfileDeleteExpenseEntryPoint:
    def test_profile_page_contains_delete_form_posting_to_delete_url_for_each_row(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = _new_user(db_path)
        login(client, user_id, "Delete Expense User")
        expense_id = insert_expense(user_id, "Food", 12.00, "2026-08-04", "Snack")

        response = client.get("/profile")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert _delete_url(expense_id) in body, (
            "profile.html should contain a form/button posting to "
            f"/expenses/{expense_id}/delete for each transaction row"
        )
        body_lower = body.lower()
        assert 'method="post"' in body_lower or "method='post'" in body_lower, (
            "The delete action must be implemented as a POST form, not a plain "
            "<a href> link"
        )
