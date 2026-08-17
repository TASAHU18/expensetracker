import database.db as db


def test_get_profile_user_happy_path(seeded):
    user = db.get_profile_user(seeded["id"])
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["initials"] == "DU"
    assert len(user["member_since"].split()) == 2  # "Month YYYY"


def test_get_profile_user_nonexistent_id(db_path):
    assert db.get_profile_user(99999) is None


def test_get_expense_totals_happy_path(seeded):
    totals = db.get_expense_totals(seeded["id"])
    assert totals["total_spent"] == 285.25
    assert totals["transaction_count"] == 8


def test_get_expense_totals_no_expenses(db_path):
    user_id = db.create_user("Fresh User", "fresh@example.com", "hash")
    totals = db.get_expense_totals(user_id)
    assert totals == {"total_spent": 0, "transaction_count": 0}


def test_get_recent_transactions_ordering_and_limit(db_path, insert_expense):
    user_id = db.create_user("Order Test", "order@example.com", "hash")
    insert_expense(user_id, "Food", 10.00, "2026-08-01", "Old")
    insert_expense(user_id, "Food", 20.00, "2026-08-05", "Newest")
    insert_expense(user_id, "Food", 15.00, "2026-08-03", "Middle")

    transactions = db.get_recent_transactions(user_id, limit=2)
    assert len(transactions) == 2
    assert transactions[0]["description"] == "Newest"
    assert transactions[1]["description"] == "Middle"


def test_get_recent_transactions_no_expenses(db_path):
    user_id = db.create_user("Empty Txns", "empty@example.com", "hash")
    assert db.get_recent_transactions(user_id) == []


def test_get_recent_transactions_null_description(db_path, insert_expense):
    user_id = db.create_user("Null Desc", "nulldesc@example.com", "hash")
    insert_expense(user_id, "Other", 5.00, "2026-08-01", None)
    transactions = db.get_recent_transactions(user_id)
    assert transactions[0]["description"] == ""


def test_get_category_breakdown_happy_path(seeded):
    categories = db.get_category_breakdown(seeded["id"])
    assert len(categories) == 7
    amounts = [c["amount"] for c in categories]
    assert amounts == sorted(amounts, reverse=True)
    assert categories[0]["name"] == "Bills"

    by_name = {c["name"]: c for c in categories}
    assert by_name["Bills"]["percent"] == 30
    assert by_name["Bills"]["width_class"] == "profile-bar-w-30"
    assert by_name["Shopping"]["percent"] == 21
    assert by_name["Shopping"]["width_class"] == "profile-bar-w-20"
    assert by_name["Other"]["percent"] == 4
    assert by_name["Other"]["width_class"] == "profile-bar-w-5"


def test_get_category_breakdown_no_expenses(db_path):
    user_id = db.create_user("Empty Cats", "emptycats@example.com", "hash")
    assert db.get_category_breakdown(user_id) == []
