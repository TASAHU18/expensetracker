# Spec: Edit Expense

## Overview
This step replaces the `GET /expenses/<id>/edit` stub with a real form for updating an existing expense. Today a logged-in user can add expenses (Step 7) and view them on `/profile`, but has no way to correct a mistake — wrong amount, wrong category, wrong date — without deleting and re-creating the row. This step adds an edit form pre-filled with the expense's current values, backend logic to validate and persist changes, and an entry point from the profile page's transaction table. It closes the correction gap before delete (Step 9) is built on top of it.

## Depends on
- Step 01 (Database setup) — `expenses` table and `get_db()`
- Step 03 (Login and Logout) — session-based auth
- Step 05 (Profile page backend routes) — `/profile` route and `get_recent_transactions()`
- Step 07 (Add expense) — `CATEGORIES`, form validation pattern, `add_expense.html` layout to mirror

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the expense's current values — logged-in, owner-only
- `POST /expenses/<int:id>/edit` — validate and persist changes to the expense — logged-in, owner-only

Both methods are handled by the same `edit_expense(id)` view, matching the `add_expense` pattern. A non-existent id, or an id belonging to another user, returns a 404 via `abort(404)` — never leak whether the id exists to a non-owner.

## Database changes
No schema changes. `expenses` already has every column this feature needs (`id`, `user_id`, `amount`, `category`, `date`, `description`).

Two new functions are needed in `database/db.py`:
- `get_expense_by_id(expense_id, user_id)` — returns the row only if it belongs to `user_id`, else `None`. Used both to populate the edit form and to authorize the POST before updating.
- `update_expense(expense_id, amount, category, expense_date, description)` — `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? WHERE id = ?`, parameterized.

`get_recent_transactions()` must also start selecting `id` (currently selects only `date, description, category, amount`) so `profile.html` has an id to link the Edit action to.

## Templates
- **Create:** `templates/edit_expense.html` — same `auth-section` / `auth-card` / `form-group` layout as `add_expense.html`, form fields pre-filled from the existing expense, submits to `POST /expenses/<id>/edit`
- **Modify:** `templates/profile.html` — add an "Edit" link/action per row in the transaction table, pointing to `url_for('edit_expense', id=txn.id)`

## Files to change
- `app.py` — replace the `edit_expense` stub with `GET`/`POST` handling
- `database/db.py` — add `get_expense_by_id()` and `update_expense()`; add `id` to `get_recent_transactions()`'s `SELECT` and returned dict
- `templates/profile.html` — add per-row Edit link
- `static/css/profile.css` — style for the new per-row action link (no existing class covers this)

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (unaffected by this feature, but preserve existing behavior)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Every DB query goes in `database/db.py`, never inline in `app.py`
- Reuse the validation logic already in `_validate_expense_form()` in `app.py` rather than duplicating it
- Ownership check is mandatory: a user must never be able to view or edit another user's expense by guessing its id — return 404, not a redirect or an error message that confirms the id exists
- On successful update, redirect to `/profile` (same as add expense)

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` for your own expense while logged in shows a form pre-filled with that expense's amount, category, date, and description
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that doesn't exist returns a 404
- [ ] Visiting `/expenses/<id>/edit` for an expense belonging to another user returns a 404
- [ ] Submitting the form with a valid amount, category, and date updates the expense and redirects to `/profile`, where the updated values are visible
- [ ] Submitting the form with an invalid amount (zero, negative, non-numeric) re-renders the form with an error and preserves the submitted values
- [ ] Submitting the form with a missing category or date re-renders the form with an error
- [ ] The transaction table on `/profile` shows an Edit link/action for each row that navigates to the correct `/expenses/<id>/edit` URL
