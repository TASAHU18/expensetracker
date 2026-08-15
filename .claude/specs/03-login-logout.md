# Spec: Login and Logout

## Overview
This step wires up real authentication for Spendly. The `GET /login` route already renders `login.html`, but there is no backend logic to verify credentials, and `GET /logout` is still a stub that returns a raw string. This step adds `POST /login` handling so a registered user can actually sign in, and implements `GET /logout` so a signed-in user can end their session. Together with Step 02 (Registration), this completes the authentication flow that later steps (profile, expenses) depend on to know who is logged in.

## Depends on
- Step 01 — Database Setup (`users` table, `get_db()` — confirmed present in `database/db.py`)
- Step 02 — Registration (`create_user()`, `get_user_by_email()`, and the `session['user_id']` convention — confirmed present in `app.py` / `database/db.py`)

## Routes
- `GET /login` — renders the login form, optionally with an authentication error — public (already implemented; only the template's hardcoded form action needs fixing)
- `POST /login` — validates credentials against the stored password hash, starts a session, redirects to `/` — public
- `GET /logout` — clears the session and redirects to `/` — logged-in (redirect to `/login` if no active session)

## Database changes
No database changes. `get_user_by_email()` already exists from Step 02 and returns the full user row, including `password_hash`. No new tables, columns, or constraints needed.

## Templates
- **Create:** none
- **Modify:** `templates/login.html` — change the hardcoded `action="/login"` to `action="{{ url_for('login') }}"`

## Files to change
- `app.py` — extend the `login` view to handle `GET` and `POST`; replace the `logout` stub with real session-clearing logic
- `database/db.py` — no changes needed; reuse existing `get_user_by_email()`
- `templates/login.html` — fix hardcoded form action to use `url_for()`

## Files to create
None

## New dependencies
No new dependencies

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — use `check_password_hash()` to verify against the stored `password_hash`, never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB access for this feature goes through `database/db.py` — no inline SQL in `app.py`
- Session must store only `user_id` — never store the password or password hash in the session
- On failed login (unknown email or wrong password), re-render `login.html` with a single generic error (e.g. "Invalid email or password") — never reveal whether the email exists
- `GET /logout` must render a template or issue a `redirect()` — never return a raw string

## Definition of done
- [ ] `GET /login` still renders the form correctly
- [ ] Submitting the seeded demo user's credentials (`demo@spendly.com` / `demo123`) logs in successfully and redirects away from `/login`
- [ ] Submitting a correct email with the wrong password re-renders `login.html` with an error and does not establish a session
- [ ] Submitting an email that doesn't exist re-renders `login.html` with the same generic error and does not establish a session
- [ ] Submitting with a missing/empty field re-renders `login.html` with an error and does not hit the database
- [ ] After successful login, `session['user_id']` is set to the correct user's id
- [ ] Visiting `GET /logout` while logged in clears the session and redirects to `/`
- [ ] After logout, the session no longer contains `user_id`
- [ ] `templates/login.html` form submits via `url_for('login')`, not a hardcoded path
