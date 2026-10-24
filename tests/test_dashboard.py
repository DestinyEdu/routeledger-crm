import re


def card_value(html, title):
    match = re.search(rf'{title}</h3>\s*<p class="value">([^<]+)</p>', html)
    assert match, f"card '{title}' not found"
    return match.group(1).strip()


def test_empty_dashboard(auth_client):
    resp = auth_client.get("/")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert card_value(html, "Funds Received") == "R 0.00"
    assert card_value(html, "Pending Verification") == "0"
    assert card_value(html, "Awaiting Payout") == "0"
    assert card_value(html, "Completed Payouts") == "0"
    assert "No transactions yet" in html


def test_dashboard_totals(auth_client, make_tx):
    make_tx(amount="1000.00", status="pending_verification")  # not counted as funds
    make_tx(amount="800.00", status="verified")
    make_tx(amount="2000.00", status="awaiting_payout")
    make_tx(amount="500.00", status="completed")

    html = auth_client.get("/").get_data(as_text=True)
    assert card_value(html, "Funds Received") == "R 3,300.00"
    assert card_value(html, "Pending Verification") == "1"
    assert card_value(html, "Awaiting Payout") == "1"
    assert card_value(html, "Completed Payouts") == "1"


def test_register_lists_transactions(auth_client, make_tx):
    make_tx(sender="Thuto S", recipient="Thabo S", amount="800.00")
    html = auth_client.get("/").get_data(as_text=True)
    assert "T-0001" in html
    assert "Thuto S" in html
    assert "Thabo S" in html


def test_cards_update_after_advancing(auth_client, make_tx):
    tx_id = make_tx(amount="250.00")
    auth_client.post(f"/transactions/{tx_id}/advance")  # -> verified
    html = auth_client.get("/").get_data(as_text=True)
    assert card_value(html, "Funds Received") == "R 250.00"
    assert card_value(html, "Pending Verification") == "0"


def test_user_input_is_escaped_in_register(auth_client, make_tx):
    make_tx(sender="<script>alert(1)</script>")
    html = auth_client.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
