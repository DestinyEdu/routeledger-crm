from urllib.parse import urlparse

import pytest

VALID_TX = {"sender_name": "John D", "recipient_name": "Mary D", "amount": "100"}


def location(resp):
    return resp.headers["Location"]


def test_dashboard_requires_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in location(resp)


def test_create_transaction_requires_login(client, tx_count):
    resp = client.post("/transactions", data=VALID_TX)
    assert resp.status_code == 302
    assert "/login" in location(resp)
    assert tx_count() == 0


def test_advance_requires_login(client, make_tx, tx_status):
    tx_id = make_tx()
    resp = client.post(f"/transactions/{tx_id}/advance")
    assert resp.status_code == 302
    assert "/login" in location(resp)
    assert tx_status(tx_id) == "pending_verification"


def test_login_success(client, user):
    resp = client.post("/login", data=user)
    assert resp.status_code == 302
    assert urlparse(location(resp)).path == "/"
    assert client.get("/").status_code == 200


def test_login_wrong_password(client, user):
    resp = client.post("/login", data={**user, "password": "wrong-password-123"})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.get_data(as_text=True)
    assert client.get("/").status_code == 302


def test_login_unknown_user_gives_same_error(client, user):
    resp = client.post("/login", data={"username": "nobody", "password": "whatever-123456"})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.get_data(as_text=True)


def test_username_is_case_insensitive(client, user):
    resp = client.post("/login", data={**user, "username": "TESTER"})
    assert resp.status_code == 302


@pytest.mark.parametrize(
    "target",
    ["https://evil.example", "//evil.example", "http://evil.example/x", "/\\evil.example"],
)
def test_login_blocks_external_redirects(client, user, target):
    resp = client.post("/login", data={**user, "next": target})
    assert resp.status_code == 302
    assert "evil.example" not in location(resp)


def test_logout_is_post_only(auth_client):
    assert auth_client.get("/logout").status_code == 405


def test_logout_ends_session(auth_client):
    assert auth_client.get("/").status_code == 200
    resp = auth_client.post("/logout")
    assert resp.status_code == 302
    assert "/login" in location(resp)
    assert auth_client.get("/").status_code == 302


def test_security_headers_present(client):
    resp = client.get("/login")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
