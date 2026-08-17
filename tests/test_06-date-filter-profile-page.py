"""
Tests for Step 6: date-range filter on the profile page.

Spec: .claude/specs/06-date-filter-profile-page.md

Scope note: this spec only documents a *custom* start_date/end_date query
param filter on GET /profile. It does not document preset ranges (e.g.
?range=month). These tests are written strictly against what the spec says
the feature should do and therefore only exercise the custom start_date /
end_date behavior.

Fixtures (`app`, `client`, `db_path`, `seeded`, `login`, `insert_expense`)
come from tests/conftest.py, which redirects database/db.py's DB_PATH to a
fresh temp file per test so each test is fully isolated.
"""

import database.db as db


# --------------------------------------------------------------------- #
# database/db.py — optional start_date / end_date parameters             #
# --------------------------------------------------------------------- #

class TestDbDateRangeFilters:
    def test_get_expense_totals_filters_to_range(self, db_path, insert_expense):
        user_id = db.create_user("Totals Range", "totals-range@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")
        insert_expense(user_id, "Bills", 45.00, "2026-07-31", "July 31 electricity")
        insert_expense(user_id, "Shopping", 50.00, "2026-08-01", "August 1 shoes")

        totals = db.get_expense_totals(user_id, start_date="2026-07-01", end_date="2026-07-31")

        assert totals["total_spent"] == 100.00, "Only the 3 July expenses should be summed"
        assert totals["transaction_count"] == 3, "Only 3 expenses fall within the July range"

    def test_get_expense_totals_boundary_dates_are_inclusive(self, db_path, insert_expense):
        user_id = db.create_user("Boundary Totals", "boundary-totals@example.com", "hash")
        insert_expense(user_id, "Food", 10.00, "2026-06-30", "Just before range")
        insert_expense(user_id, "Food", 10.00, "2026-07-01", "Start boundary")
        insert_expense(user_id, "Food", 10.00, "2026-07-31", "End boundary")
        insert_expense(user_id, "Food", 10.00, "2026-08-01", "Just after range")

        totals = db.get_expense_totals(user_id, start_date="2026-07-01", end_date="2026-07-31")

        assert totals["transaction_count"] == 2, (
            "BETWEEN must include both boundary dates and exclude the neighboring days"
        )
        assert totals["total_spent"] == 20.00

    def test_get_expense_totals_no_matches_in_range(self, db_path, insert_expense):
        user_id = db.create_user("No Match Totals", "no-match-totals@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        totals = db.get_expense_totals(user_id, start_date="2026-01-01", end_date="2026-01-31")

        assert totals == {"total_spent": 0, "transaction_count": 0}

    def test_get_expense_totals_only_start_date_supplied_is_ignored(self, db_path, insert_expense):
        user_id = db.create_user("Partial Totals", "partial-totals@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")

        filtered = db.get_expense_totals(user_id, start_date="2026-07-01", end_date=None)
        unfiltered = db.get_expense_totals(user_id)

        assert filtered == unfiltered, "Supplying only start_date must behave exactly like no filter"

    def test_get_expense_totals_only_end_date_supplied_is_ignored(self, db_path, insert_expense):
        user_id = db.create_user("Partial Totals 2", "partial-totals-2@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")

        filtered = db.get_expense_totals(user_id, start_date=None, end_date="2026-07-01")
        unfiltered = db.get_expense_totals(user_id)

        assert filtered == unfiltered, "Supplying only end_date must behave exactly like no filter"

    def test_get_recent_transactions_within_range_ordered_most_recent_first(self, db_path, insert_expense):
        user_id = db.create_user("Txn Range", "txn-range@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")
        insert_expense(user_id, "Shopping", 50.00, "2026-08-01", "August 1 shoes")

        transactions = db.get_recent_transactions(
            user_id, limit=10, start_date="2026-07-01", end_date="2026-07-31"
        )
        descriptions = [t["description"] for t in transactions]

        assert descriptions == ["July 15 cab", "July 1 lunch"], (
            "Only the July transactions should be returned, most recent first"
        )

    def test_get_recent_transactions_not_capped_when_filter_is_active(self, db_path, insert_expense):
        user_id = db.create_user("Uncapped", "uncapped@example.com", "hash")
        for day in range(1, 13):  # 12 expenses, all inside the filtered range
            insert_expense(user_id, "Other", 1.00, f"2026-05-{day:02d}", f"Item {day}")

        transactions = db.get_recent_transactions(
            user_id, limit=10, start_date="2026-05-01", end_date="2026-05-31"
        )

        assert len(transactions) == 12, (
            "Per spec, while a date filter is active the transaction list must not be capped at 10"
        )

    def test_get_recent_transactions_no_matches_in_range(self, db_path, insert_expense):
        user_id = db.create_user("Empty Range Txn", "empty-range-txn@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        transactions = db.get_recent_transactions(
            user_id, start_date="2026-01-01", end_date="2026-01-31"
        )

        assert transactions == []

    def test_get_category_breakdown_within_range_excludes_out_of_range_categories(
        self, db_path, insert_expense
    ):
        user_id = db.create_user("Category Range", "category-range@example.com", "hash")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")
        insert_expense(user_id, "Bills", 45.00, "2026-07-31", "July 31 electricity")
        insert_expense(user_id, "Shopping", 50.00, "2026-08-01", "August outside range")

        categories = db.get_category_breakdown(
            user_id, start_date="2026-07-01", end_date="2026-07-31"
        )
        names = {c["name"] for c in categories}

        assert names == {"Food", "Transport", "Bills"}, (
            "Shopping falls outside the range and must be excluded from the breakdown"
        )

    def test_get_category_breakdown_percentages_sum_to_100_within_range(self, db_path, insert_expense):
        user_id = db.create_user("Category Percent", "category-percent@example.com", "hash")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")
        insert_expense(user_id, "Bills", 45.00, "2026-07-31", "July 31 electricity")
        insert_expense(user_id, "Shopping", 999.00, "2026-08-01", "August outside range")

        categories = db.get_category_breakdown(
            user_id, start_date="2026-07-01", end_date="2026-07-31"
        )

        assert sum(c["percent"] for c in categories) == 100, (
            "Category percentages within the filtered range must still sum to 100"
        )

    def test_get_category_breakdown_no_matches_in_range(self, db_path, insert_expense):
        user_id = db.create_user("Empty Range Cat", "empty-range-cat@example.com", "hash")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        categories = db.get_category_breakdown(
            user_id, start_date="2026-01-01", end_date="2026-01-31"
        )

        assert categories == []


# --------------------------------------------------------------------- #
# GET /profile — custom start_date / end_date query params               #
# --------------------------------------------------------------------- #

class TestProfileDateFilterRoute:
    def test_no_query_params_behaves_like_the_unfiltered_view(self, app, client, seeded, login):
        login(client, seeded["id"], seeded["name"])

        response = client.get("/profile")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "₹285.25" in body, "Visiting /profile with no params must show all-time totals, unchanged"

    def test_filtered_url_while_logged_out_redirects_to_login(self, app, client):
        response = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")

        assert response.status_code == 302
        assert response.headers["Location"] == "/login", (
            "A filtered profile URL must require auth just like the unfiltered route"
        )

    def test_custom_range_filters_stats_transactions_and_categories(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Range User", "range-user@example.com", "hash")
        login(client, user_id, "Range User")

        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Food", 25.00, "2026-07-01", "July 1 lunch")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")
        insert_expense(user_id, "Bills", 45.00, "2026-07-31", "July 31 electricity")
        insert_expense(user_id, "Shopping", 50.00, "2026-08-01", "August 1 shoes")

        response = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "₹100.00" in body, "Total spent should reflect only the 3 expenses within the July range"
        assert "July 1 lunch" in body
        assert "July 15 cab" in body
        assert "July 31 electricity" in body
        assert "June groceries" not in body, "Expense before the range must be excluded"
        assert "August 1 shoes" not in body, "Expense after the range must be excluded"

    def test_filtered_transaction_list_is_not_capped_at_ten(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Uncapped Route", "uncapped-route@example.com", "hash")
        login(client, user_id, "Uncapped Route")

        for day in range(1, 13):  # 12 expenses, all inside the filtered range
            insert_expense(user_id, "Other", 1.00, f"2026-05-{day:02d}", f"Item {day}")

        response = client.get("/profile?start_date=2026-05-01&end_date=2026-05-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        for day in range(1, 13):
            assert f"Item {day}" in body, (
                f"Item {day} should be visible — a date filter must show every matching "
                "transaction, not just the first 10"
            )

    def test_zero_matches_in_range_does_not_leak_other_data(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Empty Range Route", "empty-range-route@example.com", "hash")
        login(client, user_id, "Empty Range Route")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        response = client.get("/profile?start_date=2026-01-01&end_date=2026-01-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)

        assert "₹0.00" in body, "Stats must show zero spend for a range with no matching expenses"
        assert "June groceries" not in body, "Out-of-range expense must not appear in the table"

        empty_state_phrases = ("no transactions", "no expenses", "no results", "nothing to show", "no matching")
        assert any(phrase in body.lower() for phrase in empty_state_phrases), (
            "Spec requires an empty-state message in place of the table when the active "
            "filter matches zero transactions"
        )

    def test_end_date_before_start_date_falls_back_to_unfiltered_view(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Invalid Range", "invalid-range@example.com", "hash")
        login(client, user_id, "Invalid Range")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")

        response = client.get("/profile?start_date=2026-07-31&end_date=2026-07-01")

        assert response.status_code == 200, "An invalid range (end before start) must not crash the app"
        body = response.get_data(as_text=True)

        assert "₹50.00" in body, "Falling back to the unfiltered view should show the true all-time total"
        assert "June groceries" in body
        assert "July 15 cab" in body

        validation_phrases = ("invalid", "must be", "before", "after", "error")
        assert any(phrase in body.lower() for phrase in validation_phrases), (
            "Spec requires an inline validation message when end date is before start date"
        )

    def test_malformed_dates_do_not_500_and_fall_back_to_unfiltered_view(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Malformed Dates", "malformed-dates@example.com", "hash")
        login(client, user_id, "Malformed Dates")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        response = client.get("/profile?start_date=notadate&end_date=alsonotadate")

        assert response.status_code == 200, "Malformed dates must never raise a 500"
        body = response.get_data(as_text=True)
        assert "₹20.00" in body, "Should fall back to showing the unfiltered all-time total"
        assert "June groceries" in body

    def test_only_start_date_supplied_falls_back_to_unfiltered_view(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Partial Route Start", "partial-route-start@example.com", "hash")
        login(client, user_id, "Partial Route Start")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        response = client.get("/profile?start_date=2026-07-01")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "₹20.00" in body, "Supplying only start_date must be treated as no filter at all"
        assert "June groceries" in body

    def test_only_end_date_supplied_falls_back_to_unfiltered_view(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Partial Route End", "partial-route-end@example.com", "hash")
        login(client, user_id, "Partial Route End")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")

        response = client.get("/profile?end_date=2026-07-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "₹20.00" in body, "Supplying only end_date must be treated as no filter at all"
        assert "June groceries" in body

    def test_active_range_is_displayed_near_the_panel_titles(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Display Range", "display-range@example.com", "hash")
        login(client, user_id, "Display Range")
        insert_expense(user_id, "Food", 25.00, "2026-07-15", "Mid July lunch")

        response = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "Jul 01, 2026" in body, "Active start date should be displayed near the panel titles"
        assert "Jul 31, 2026" in body, "Active end date should be displayed near the panel titles"

    def test_date_inputs_are_prefilled_from_query_params(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Prefill User", "prefill-user@example.com", "hash")
        login(client, user_id, "Prefill User")
        insert_expense(user_id, "Food", 25.00, "2026-07-15", "Mid July lunch")

        response = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "2026-07-01" in body, "start_date query param should be echoed back into the filter form"
        assert "2026-07-31" in body, "end_date query param should be echoed back into the filter form"

    def test_clearing_filter_returns_to_the_unfiltered_view(
        self, app, client, db_path, login, insert_expense
    ):
        user_id = db.create_user("Clear Filter User", "clear-filter@example.com", "hash")
        login(client, user_id, "Clear Filter User")
        insert_expense(user_id, "Food", 20.00, "2026-06-15", "June groceries")
        insert_expense(user_id, "Transport", 30.00, "2026-07-15", "July 15 cab")

        filtered_response = client.get("/profile?start_date=2026-07-01&end_date=2026-07-31")
        assert "June groceries" not in filtered_response.get_data(as_text=True)

        # "Clear filter" is a plain link back to the bare /profile URL.
        cleared_response = client.get("/profile")

        assert cleared_response.status_code == 200
        body = cleared_response.get_data(as_text=True)
        assert "June groceries" in body, "Clearing the filter should bring back all-time transactions"
        assert "July 15 cab" in body
