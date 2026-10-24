import re

from app.models import Transaction, User, db

from conftest import PASSWORD

CREDS = {"username": "tester", "password": PASSWORD}
VALID_TX = {"sender_name": "John D", "recipient_name": "Mary D", "amount": "100"}


def add_user(app):
    with app.app_context():
        u = User(username="tester")
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.commit()


def token_from(client, path):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def count(app):
    with app.app_context():
        return Transaction.query.count()


def test_login_rejects_missing_token(csrf_app):
    add_user(csrf_app)
    client = csrf_app.test_client()
    assert client.post("/login", data=CREDS).status_code == 400


def test_login_accepts_valid_token(csrf_app):
    add_user(csrf_app)
    client = csrf_app.test_client()
    token = token_from(client, "/login")
    resp = client.post("/login", data={**CREDS, "csrf_token": token})
    assert resp.status_code == 302


def test_transaction_post_needs_token(csrf_app):
    add_user(csrf_app)
    client = csrf_app.test_client()
    client.post("/login", data={**CREDS, "csrf_token": token_from(client, "/login")})

    # No token: rejected, nothing saved
    assert client.post("/transactions", data=VALID_TX).status_code == 400
    assert count(csrf_app) == 0

    # With token: accepted
    token = token_from(client, "/")
    resp = client.post("/transactions", data={**VALID_TX, "csrf_token": token})
    assert resp.status_code == 302
    assert count(csrf_app) == 1


def test_logout_needs_token(csrf_app):
    add_user(csrf_app)
    client = csrf_app.test_client()
    client.post("/login", data={**CREDS, "csrf_token": token_from(client, "/login")})
    assert client.post("/logout").status_code == 400
    assert client.get("/").status_code == 200  # still signed in
