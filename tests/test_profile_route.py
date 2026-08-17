import database.db as db


def test_profile_unauthenticated_redirects_to_login(app, client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"


def test_profile_authenticated_shows_seeded_data(app, client, seeded, login):
    login(client, seeded["id"], seeded["name"])
    response = client.get("/profile")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹285.25" in body
    assert "profile-badge-bills" in body


def test_profile_fresh_user_has_no_expenses(app, client, db_path, login):
    user_id = db.create_user("Fresh User", "fresh@example.com", "hash")
    login(client, user_id, "Fresh User")

    response = client.get("/profile")
    assert response.status_code == 200

    body = response.get_data(as_text=True)
    assert "₹0.00" in body
    assert "—" in body


def test_profile_stale_session_redirects_to_login(app, client, db_path, login):
    login(client, 99999, "Ghost")
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
