from decimal import Decimal

import pytest

from app import STATUS_FLOW
from app.models import Transaction, db

VALID = {"sender_name": "John D", "recipient_name": "Mary D", "amount": "1234.50"}


def test_create_transaction(auth_client, app):
    resp = auth_client.post("/transactions", data=VALID)
    assert resp.status_code == 302
    with app.app_context():
        tx = Transaction.query.one()
        assert tx.sender_name == "John D"
        assert tx.recipient_name == "Mary D"
        assert tx.amount == Decimal("1234.50")
        assert tx.currency == "ZAR"
        assert tx.status == "pending_verification"
        assert tx.reference.startswith("RL-")


def test_names_are_trimmed(auth_client, app):
    auth_client.post("/transactions", data={**VALID, "sender_name": "  John D  "})
    with app.app_context():
        assert Transaction.query.one().sender_name == "John D"


@pytest.mark.parametrize(
    "override",
    [
        {"sender_name": ""},
        {"sender_name": "   "},
        {"recipient_name": ""},
        {"amount": ""},
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "abc"},
        {"amount": "nan"},
        {"amount": "inf"},
        {"amount": "10000000000"},
        {"sender_name": "x" * 121},
        {"recipient_name": "x" * 121},
    ],
)
def test_invalid_input_is_rejected(auth_client, tx_count, override):
    resp = auth_client.post("/transactions", data={**VALID, **override})
    assert resp.status_code == 400
    assert tx_count() == 0


def test_status_flow_order():
    assert STATUS_FLOW == [
        "pending_verification",
        "verified",
        "awaiting_payout",
        "completed",
    ]


def test_advance_walks_through_every_status(auth_client, make_tx, tx_status):
    tx_id = make_tx()
    seen = [tx_status(tx_id)]
    for _ in range(4):
        auth_client.post(f"/transactions/{tx_id}/advance")
        seen.append(tx_status(tx_id))
    # Moves one step at a time, then stays at completed
    assert seen == [
        "pending_verification",
        "verified",
        "awaiting_payout",
        "completed",
        "completed",
    ]


def test_advance_unknown_transaction_is_404(auth_client):
    assert auth_client.post("/transactions/9999/advance").status_code == 404


def test_advance_is_post_only(auth_client, make_tx):
    tx_id = make_tx()
    assert auth_client.get(f"/transactions/{tx_id}/advance").status_code == 405
