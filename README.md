# RouteLedger CRM

A transaction-management dashboard built with Flask. It tracks incoming funds and payout progress through a fixed set of statuses, behind a login.

> **Demonstration project.** No real bank or payment systems are connected. It is in early development and is not production-ready.

## Features

- **Operations dashboard** with four live summary cards: Funds Received, Pending Verification, Awaiting Payout, and Completed Payouts
- **Transaction register** showing the 50 most recent transactions, with local-time (Africa/Johannesburg) timestamps
- **Add transactions** through a validated form (required names, positive amounts, stored as exact decimals)
- **Fixed status workflow**: `pending_verification` → `verified` → `awaiting_payout` → `completed`, advanced one step at a time
- **Auto-generated references** in the form `RL-XXXXXXXX`
- **Authentication**: login and logout with hashed passwords, and every dashboard and transaction route requires a signed-in user
- **CSRF protection** on all forms
- No public sign-up: users are created from the command line

## Tech stack

- Python 3.14 (developed on Ubuntu)
- Flask
- Flask-SQLAlchemy with SQLite
- Flask-Login
- Flask-WTF (CSRF protection)

## Project structure

```
routeledger-crm/
├── app/
│   ├── __init__.py        # app factory, routes, login, CLI command
│   ├── models.py          # User, Transaction, TransactionStatus
│   ├── static/            # style.css, app.js
│   └── templates/         # index.html (dashboard), login.html
├── tests/                 # pytest test suite
├── requirements.txt
└── run.py                 # entry point
```

## Getting started

```bash
# 1. Clone
git clone https://github.com/DestinyEdu/routeledger-crm.git
cd routeledger-crm

# 2. Create a virtual environment
#    (on Ubuntu you may first need: sudo apt install python3-venv)
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your first user (prompts for a password, minimum 12 characters)
flask --app run create-user admin

# 5. Run the app
python run.py
```

Then open <http://127.0.0.1:5000> and sign in.

## Running the tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests use an in-memory database, so your real data is never touched.

## Configuration

| Setting | How it works |
| --- | --- |
| Secret key | Set the `ROUTELEDGER_SECRET_KEY` environment variable, or one is generated automatically and saved to `instance/secret_key` |
| Database | SQLite file at `instance/routeledger.db`, created on first run |

The `instance/` folder is excluded from git, so the database and secret key are never committed.

## Security notes

Implemented:

- Passwords are hashed, never stored in plain text
- CSRF tokens on every state-changing form; logout is POST-only
- Session cookies are HttpOnly and SameSite=Lax, with the session reset on login
- Login redirects only to paths on the same site
- Login errors don't reveal whether a username exists
- Basic security headers on all responses

Not implemented yet:

- Login rate limiting or lockout
- HTTPS and secure cookies (required before any real deployment)
- Audit trail of who created or changed each transaction

Do not run with `debug=True` on any machine other people can reach.

## Roadmap

- [x] Automated tests (pytest) for the status flow, dashboard totals, validation, and access control
- [ ] Audit log of transaction changes
- [ ] Login rate limiting
- [ ] Transaction search and filtering
- [ ] Deployment configuration with HTTPS

## License

Not yet specified.
