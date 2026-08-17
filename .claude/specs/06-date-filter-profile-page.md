# Spec: Date Filter for Profile Page

## Overview
Step 6 adds an optional date-range filter to the `/profile` page. Today the
profile page always shows all-time summary stats, the 10 most recent
transactions, and an all-time category breakdown. This step lets a logged-in
user narrow those same three sections down to a specific date range (e.g.
"this month" or a custom start/end date) so they can answer questions like
"how much did I spend in July?" without leaving the page. The filter is
expressed as query parameters on the existing `GET /profile` route, so
filtered views stay bookmarkable and shareable.

## Depends on
- Step 4: Profile page static UI (template structure for stats, transactions, breakdown)
- Step 5: Profile page backend routes (`/profile` already renders live data from `database/db.py`)

## Routes
No new routes. The existing route is extended:
- `GET /profile` — now accepts optional `start_date` and `end_date` query
  params (`YYYY-MM-DD`). When both are present and valid, stats,
  transactions, and category breakdown are scoped to that range. When
  absent, invalid, or malformed, behavior is unchanged from Step 5
  (all-time stats, last 10 transactions). Access level: logged-in.

## Database changes
No schema changes. `expenses.date` is already stored as `TEXT` in
`YYYY-MM-DD` format, which sorts and compares correctly with `BETWEEN` in
SQLite. Existing query functions in `database/db.py` gain optional
`start_date` / `end_date` parameters:
- `get_expense_totals(user_id, start_date=None, end_date=None)`
- `get_recent_transactions(user_id, limit=10, start_date=None, end_date=None)`
- `get_category_breakdown(user_id, start_date=None, end_date=None)`

When both dates are provided, add `AND date BETWEEN ? AND ?` to each query
using parameterized placeholders. When not provided, queries behave exactly
as they do today.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter form above the "Recent transactions" panel with two
    `<input type="date">` fields (`start_date`, `end_date`), an "Apply"
    submit button, and a "Clear filter" link. Form uses `method="GET"` and
    `action="{{ url_for('profile') }}"` so the filter round-trips through
    the URL.
  - Pre-fill the two date inputs from the current query params so the
    filter state is visible after applying it.
  - When a filter is active, show the active range near the panel titles
    (e.g. "Jul 01, 2026 – Jul 31, 2026").
  - When a filter is active and no transactions match, show an empty-state
    message in place of the table instead of an empty `<tbody>`.
  - If the submitted range is invalid (end before start, or unparseable),
    show an inline validation message and fall back to the unfiltered view.

## Files to change
- `app.py` — `profile()` view reads `start_date` / `end_date` from
  `request.args`, validates them, and passes them through to the three
  `database/db.py` query functions; builds a `filter` context dict
  (`active`, `start_date`, `end_date`, `error`) for the template
- `database/db.py` — extend `get_expense_totals`, `get_recent_transactions`,
  `get_category_breakdown` with optional date-range parameters
- `templates/profile.html` — add the filter form, active-range display,
  empty state, and validation message
- `static/css/profile.css` — style the filter form using existing CSS
  variables (no hardcoded hex values, no inline styles)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format dates into SQL
- Passwords hashed with werkzeug (unchanged by this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate `start_date` / `end_date` server-side even though they come from
  a `<input type="date">` — the query string can be edited or tampered with
  directly
- Malformed or partially-supplied dates (e.g. only `start_date`, or a value
  that isn't a valid `YYYY-MM-DD` date) must never raise a 500 — ignore the
  filter and fall back to the unfiltered, all-time view
- If `start_date` is after `end_date`, ignore the filter, fall back to the
  unfiltered view, and surface a validation message on the page
- The three profile sections (stats, transactions, category breakdown) must
  always reflect the same filter state — never show one filtered and
  another unfiltered
- While a date filter is active, the transactions list is not capped at 10
  — show every matching transaction so the range the user asked for is
  fully represented
- Category breakdown percentages must still sum to 100 within the filtered
  range, using the same integer-rounding rule as Step 5

## Definition of done
- [ ] Visiting `/profile` with no query params behaves exactly as before
      Step 6 (last 10 transactions, all-time stats and breakdown)
- [ ] Submitting a start and end date reloads
      `/profile?start_date=...&end_date=...` showing only transactions
      within that range
- [ ] Total spent, transaction count, and top category reflect only
      expenses inside the selected range
- [ ] Category breakdown reflects only expenses inside the selected range
      and percentages sum to 100%
- [ ] A date range with zero matching expenses shows an empty-state
      message instead of a blank table
- [ ] An end date earlier than the start date does not crash the app —
      the page reloads unfiltered with a validation message
- [ ] `/profile?start_date=notadate&end_date=alsonotadate` loads the
      unfiltered profile page without a 500 error
- [ ] Clicking "Clear filter" returns to the unfiltered, all-time view
- [ ] Visiting a filtered profile URL while logged out redirects to
      `/login` (302), same as the unfiltered route
