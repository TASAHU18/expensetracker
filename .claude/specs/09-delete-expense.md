# Spec: Delete Expense

## Overview
This feature completes the core expense-tracking CRUD loop by letting a logged-in user permanently remove one of their own expenses. It builds directly on the add (Step 7) and edit (Step 8) flows, reusing the same ownership-scoped access pattern established by `get_expense_by_id` and `update_expense`. The delete action is triggered from the "Recent transactions" table on the profile page, next to the existing Edit link, and requires a client-side confirmation before the request is sent so a misclick can't destroy data.

## Depends on
- Step 1 (Database Setup) — `get_db()`, `expenses` table, FK pragma
- Step 3 (Login and Logout) — `session["user_id"]` auth pattern
- Step 5 (Backend Connection) — profile page rendering the transactions table
- Step 8 (Edit Expense) — establishes the ownership-scoped mutation pattern (`WHERE id = ? AND user_id = ?`) this spec reuses

## Routes
- `POST /expenses/<int:id>/delete` — deletes the expense if it belongs to the logged-in user, then redirects to `profile` — logged-in only

The existing stub is a bare `GET` route (`app.py` lines 367–369) that returns a raw string. It must be replaced entirely — GET is not retained, since deletion must never be triggered by a simple link/prefetch. Unauthenticated requests redirect to `login` (same pattern as `add_expense`/`edit_expense`). Requests for an `id` that doesn't exist or isn't owned by the current user must `abort(404)`, matching `edit_expense`'s existing behavior.

## Database changes
No schema changes — the `expenses` table (see `database/db.py` lines 47–58) already supports this.

New function needed in `database/db.py`:
- `delete_expense(expense_id, user_id)` — `DELETE FROM expenses WHERE id = ? AND user_id = ?`, parameterized, ownership-scoped exactly like `update_expense`. Should commit and return whether a row was actually deleted (e.g. via `cursor.rowcount`) so the route can distinguish "not found/not yours" and call `abort(404)`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html` — in the `profile-table-action` cell (lines 94–96), add a Delete action next to the existing Edit link. Implement it as a small inline `<form method="POST" action="{{ url_for('delete_expense', id=txn.id) }}">` with a submit button, not a plain `<a href>`, since deletion must be a POST.

## Files to change
- `app.py` — replace the `delete_expense` stub with the real implementation (auth check, ownership lookup/404, call `delete_expense` DB helper, redirect to `profile`)
- `database/db.py` — add the `delete_expense(expense_id, user_id)` helper
- `templates/profile.html` — add the Delete form/button to the transactions table
- `static/js/main.js` — add a vanilla JS confirmation (`confirm()`) on submit of any delete form, so the user must confirm before the request is sent
- `static/css/style.css` — style the new delete button consistently with the existing Edit link, using existing CSS variables

## Files to create
None.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (unaffected by this feature, but keep as a standing rule)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Delete must be a `POST` request, never a `GET` link, to avoid accidental/CSRF-via-link deletion
- Ownership must be enforced in the SQL `WHERE` clause (`user_id = ?`), not just checked in Python after the fact
- Client-side confirmation (`confirm()`) is required before the delete form submits — vanilla JS only, in `static/js/main.js`
- DB logic stays in `database/db.py` — no inline SQL in `app.py`
- Unauthenticated access redirects to `login`; deleting another user's or a nonexistent expense returns `404` via `abort(404)`

## Definition of done
- [ ] Visiting `/expenses/<id>/delete` with `GET` no longer works (returns 405, not the old stub string)
- [ ] Logged out, submitting a delete form for any expense redirects to `/login`
- [ ] Logged in, clicking Delete on a transaction shows a browser confirmation dialog before anything happens
- [ ] Confirming the dialog removes the expense from the database and redirects back to `/profile`, where the row no longer appears
- [ ] Cancelling the confirmation dialog leaves the expense untouched
- [ ] Attempting to delete another user's expense (e.g. by crafting the URL for an id owned by a different account) returns `404`
- [ ] Attempting to delete a nonexistent expense id returns `404`
- [ ] `pytest` passes with no regressions in existing add/edit/profile tests
