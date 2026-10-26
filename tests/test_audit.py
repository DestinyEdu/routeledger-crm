import pytest

from app.models import AuditLog, db

VALID = {"sender_name": "John D", "recipient_name": "Mary D", "amount": "1234.50"}


def rows(app, action=None):
    with app.app_context():
        query = AuditLog.query.order_by(AuditLog.id)
        if action:
            query = query.filter_by(action=action)
        return [
            {
                "action": r.action,
                "username": r.username,
                "reference": r.transaction_reference,
                "detail": r.detail,
                "transaction_id": r.transaction_id,
            }
            for r in query.all()
        ]


def test_login_is_recorded(app, client, user):
    client.post("/login", data=user)
    entries = rows(app)
    assert [e["action"] for e in entries] == ["auth.login"]
    assert entries[0]["username"] == "tester"


def test_failed_login_is_recorded(app, client, user):
    client.post("/login", data={**user, "password": "wrong-password-123"})
    client.post("/login", data={"username": "nobody", "password": "wrong-password-123"})
    entries = rows(app, "auth.login_failed")
    assert [(e["username"], e["detail"]) for e in entries] == [
        ("tester", "bad password"),
        ("nobody", "unknown user"),
    ]


def test_logout_is_recorded(app, auth_client):
    auth_client.post("/logout")
    assert [e["action"] for e in rows(app)] == ["auth.login", "auth.logout"]


def test_transaction_creation_is_recorded(app, auth_client):
    auth_client.post("/transactions", data=VALID)
    (entry,) = rows(app, "transaction.created")
    assert entry["username"] == "tester"
    assert entry["reference"].startswith("RL-")
    assert "ZAR 1,234.50" in entry["detail"]
    assert entry["transaction_id"] is not None


def test_status_change_is_recorded(app, auth_client, make_tx):
    make_tx()
    auth_client.post("/transactions/1/advance")
    (entry,) = rows(app, "transaction.advanced")
    assert entry["username"] == "tester"
    assert entry["reference"] == "T-0001"
    assert entry["detail"] == "pending_verification -> verified"


def test_advancing_a_completed_transaction_logs_nothing(app, auth_client, make_tx):
    tx_id = make_tx(status="completed")
    auth_client.post(f"/transactions/{tx_id}/advance")
    assert rows(app, "transaction.advanced") == []


def test_rejected_input_logs_nothing(app, auth_client):
    auth_client.post("/transactions", data={**VALID, "amount": "0"})
    assert rows(app, "transaction.created") == []


def test_audit_page_requires_login(client):
    resp = client.get("/audit")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_audit_page_lists_events_and_escapes_html(auth_client):
    auth_client.post("/transactions", data={**VALID, "sender_name": "<b>x</b>"})
    html = auth_client.get("/audit").get_data(as_text=True)
    assert "transaction.created" in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_audit_entries_cannot_be_edited(app, auth_client):
    with app.app_context():
        entry = AuditLog.query.first()
        entry.detail = "tampered"
        with pytest.raises(RuntimeError):
            db.session.commit()
        db.session.rollback()


def test_audit_entries_cannot_be_deleted(app, auth_client):
    with app.app_context():
        db.session.delete(AuditLog.query.first())
        with pytest.raises(RuntimeError):
            db.session.commit()
        db.session.rollback()
