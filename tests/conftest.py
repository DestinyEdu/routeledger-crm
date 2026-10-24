import itertools
from decimal import Decimal

import pytest

from app import create_app
from app.models import Transaction, TransactionStatus, User, db

PASSWORD = "correct-horse-battery"


def _build_app(csrf):
    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": csrf,
        }
    )


def _teardown(app):
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app():
    """App with CSRF checks off, for testing behaviour."""
    app = _build_app(csrf=False)
    yield app
    _teardown(app)


@pytest.fixture
def csrf_app():
    """App with CSRF checks on, for testing the protection itself."""
    app = _build_app(csrf=True)
    yield app
    _teardown(app)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    with app.app_context():
        u = User(username="tester")
        u.set_password(PASSWORD)
        db.session.add(u)
        db.session.commit()
    return {"username": "tester", "password": PASSWORD}


@pytest.fixture
def auth_client(client, user):
    client.post("/login", data=user)
    return client


@pytest.fixture
def make_tx(app):
    counter = itertools.count(1)

    def _make(
        amount="100.00",
        status=TransactionStatus.PENDING_VERIFICATION.value,
        sender="Sender",
        recipient="Recipient",
    ):
        with app.app_context():
            tx = Transaction(
                reference=f"T-{next(counter):04d}",
                sender_name=sender,
                recipient_name=recipient,
                amount=Decimal(amount),
                status=status,
            )
            db.session.add(tx)
            db.session.commit()
            return tx.id

    return _make


@pytest.fixture
def tx_status(app):
    def _status(tx_id):
        with app.app_context():
            return db.session.get(Transaction, tx_id).status

    return _status


@pytest.fixture
def tx_count(app):
    def _count():
        with app.app_context():
            return Transaction.query.count()

    return _count
