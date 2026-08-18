# Spec: Add Expense

## Overview
This step replaces the `GET /expenses/add` stub with a real form for logging a new expense. Today a logged-in user can view their transaction history on `/profile` but has no way to create one — every row currently on the page comes from `seed_db()`. This step adds the form and the backend logic to validate and persist a new expense row against the fixed category list, closing the most basic gap in the expense-tracking loop before edit (Step 8) and delete (Step 9) are built on top of it.

## Depends on
- Step 01 — Database Setup (`expenses` table, `get_db()` — confirmed present in `database/db.py`)
- Step 03 — Login and Logout (`session["user_id"]` convention — confirmed present in `app.py`)
- Step 05 — Profile Page Backend Routes (`/profile` renders live transactions the new expense should appear in)

## Routes
- `GET /expenses/add` — renders the add-expense form, optionally with a validation error — logged-in (redirect to `/login` if not authenticated)
- `POST /expenses/add` — validates input, inserts the new expense for the current user, redirects to `/profile` — logged-in (redirect to `/login` if not authenticated)

## Database changes
No schema changes. The `expenses` table already has all required columns (`user_id`, `amount`, `category`, `date`, `description`) from Step 01. One new function is added to `database/db.py`:
- `create_expense(user_id, amount, category, expense_date, description)` — parameterized `INSERT` into `expenses`, returns the new row id

## Templates
- **Create:** `templates/add_expense.html` — form with `amount` (number input), `category` (`<select>` populated from `database.db.CATEGORIES`), `date` (`<input type="date">`, defaulting to today), `description` (optional text input); reuses the existing `.form-group` / `.form-input` / `.btn-submit` classes already established in `login.html` / `register.html`; displays a validation error in the same style as `.auth-error`
- **Modify:** `templates/profile.html` — add an "Add Expense" link/button (using the existing `.btn-primary` class) near the transaction history panel, pointing to `{{ url_for('add_expense') }}`

## Files to change
- `app.py` — replace the `add_expense` stub with a real view handling `GET` and `POST`, guarded by the same `session.get("user_id")` check used by `/profile`
- `database/db.py` — add `create_expense()`
- `templates/profile.html` — add the "Add Expense" entry point described above

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (unchanged by this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access for this feature goes through `database/db.py` — no inline SQL in `app.py`
- `category` must be validated server-side against `database.db.CATEGORIES` — reject any value not in that fixed list, even though the form uses a `<select>`
- `amount` must be validated server-side as a positive number — reject zero, negative, or non-numeric input
- `date` must be validated server-side as a valid `YYYY-MM-DD` date — reject malformed or missing values
- `description` is optional; store `None`/empty rather than a placeholder string when blank
- On any validation failure, re-render `add_expense.html` with an error and the previously entered values — never lose user input or raise an unhandled exception
- On success, redirect to `/profile` (not back to `/expenses/add`) so the new expense is visible immediately

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in returns HTTP 200 and shows the form
- [ ] Submitting a valid amount, category, date, and description creates a new row in `expenses` linked to the current user
- [ ] After successful submission, the browser redirects to `/profile` and the new expense appears in the transaction list and updates the summary stats
- [ ] Submitting a negative or zero amount re-renders the form with an error and does not create a row
- [ ] Submitting a category not in the fixed list re-renders the form with an error and does not create a row
- [ ] Submitting an invalid or missing date re-renders the form with an error and does not create a row
- [ ] Submitting with description left blank succeeds and stores it as empty/`None`
- [ ] `POST /expenses/add` while logged out redirects to `/login` and does not create a row
- [ ] `templates/profile.html` shows a working "Add Expense" link that navigates to `/expenses/add`
