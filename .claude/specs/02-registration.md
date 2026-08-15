# Spec: Registration

## Overview
This step wires up real account creation for Spendly. The `GET /register` route already renders the `register.html` form, but there is no backend logic to accept a submission, validate it, hash the password, and persist a new user. This step adds `POST /register` handling so a visitor can actually create an account, and establishes a session so the app knows who is logged in for later steps (profile, expenses).

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()`, `init_db()`, `seed_db()` must exist and work — confirmed present in `database/db.py`)

## Routes
- `GET /register` — renders the registration form, optionally with a validation/duplicate-email error — public
- `POST /register` — validates input, hashes the password, inserts the new user, starts a session, redirects to `/` — public

## Database changes
No database changes. The `users` table already has the required columns (`id`, `name`, `email`, `password_hash`, `created_at`) from Step 01. No new tables, columns, or constraints needed.

## Templates
- **Create:** none
- **Modify:** `templates/register.html` — change the hardcoded `action="/register"` to `action="{{ url_for('register') }}"`; the existing `{% if error %}` block already supports displaying validation/duplicate-email errors, no structural change needed there; add a `confirm_password` field (same `.form-group`/`.form-input` markup as `password`) so the user re-enters their password before submitting

## Files to change
- `app.py` — add `app.secret_key` (via `os.urandom`), import `request`, `redirect`, `url_for`, `session` from Flask; extend the `register` view to handle `GET` and `POST`
- `database/db.py` — add two functions:
  - `get_user_by_email(email)` — parameterized `SELECT` returning a single row or `None`
  - `create_user(name, email, password_hash)` — parameterized `INSERT`, returns the new user id
- `templates/register.html` — fix hardcoded form action to use `url_for()`

## Files to create
None

## New dependencies
No new dependencies

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`, `method="pbkdf2:sha256"` to match `seed_db()`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access for this feature goes through `database/db.py` — no inline SQL in `app.py`
- Validate on the server even though the form has `required`/`type=email` attributes client-side
- Duplicate email must re-render `register.html` with an `error` message, not raise an unhandled exception
- Session must store only `user_id` — never store the password or password hash in the session
- `confirm_password` is compared against `password` server-side and is never persisted or hashed itself

## Definition of done
- [ ] `GET /register` still renders the form correctly
- [ ] Submitting valid name/email/password/confirm_password creates a new row in `users` with a hashed (not plaintext) password
- [ ] Submitting an email that already exists re-renders the form with an error and does not create a duplicate row
- [ ] Submitting with a missing/empty field (including `confirm_password`) re-renders the form with an error and does not hit the database
- [ ] Submitting a `password`/`confirm_password` pair that don't match re-renders the form with an error and does not hit the database
- [ ] After successful registration, a session is established (`session['user_id']` set) and the browser is redirected away from `/register`
- [ ] Restarting the app does not lose previously registered users (data persists in `expense_tracker.db`)
- [ ] All new queries in `database/db.py` use `?` placeholders, no f-strings in SQL
