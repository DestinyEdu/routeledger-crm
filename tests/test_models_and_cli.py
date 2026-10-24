import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Transaction, User, db

from conftest import PASSWORD


def test_password_is_hashed_and_verified():
    u = User(username="x")
    u.set_password("a-long-test-password")
    assert u.password_hash != "a-long-test-password"
    assert u.check_password("a-long-test-password")
    assert not u.check_password("something-else")


def test_transaction_reference_must_be_unique(app):
    with app.app_context():
        for _ in range(2):
            db.session.add(
                Transaction(
                    reference="DUP-1",
                    sender_name="A",
                    recipient_name="B",
                    amount=1,
                )
            )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_create_user_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-user", "Alice"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = User.query.filter_by(username="alice").one()
        assert user.check_password(PASSWORD)


def test_create_user_rejects_short_password(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-user", "bob"], input="short\nshort\n")
    assert result.exit_code != 0
    assert "at least 12" in result.output
    with app.app_context():
        assert User.query.filter_by(username="bob").count() == 0


def test_create_user_rejects_duplicates(app, user):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-user", "tester"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert result.exit_code != 0
    assert "already exists" in result.output
