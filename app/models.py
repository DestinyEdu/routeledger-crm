from datetime import datetime, timezone
from enum import Enum

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class TransactionStatus(str, Enum):
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    AWAITING_PAYOUT = "awaiting_payout"
    COMPLETED = "completed"


def utcnow():
    return datetime.now(timezone.utc)


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(32), unique=True, nullable=False, index=True)
    sender_name = db.Column(db.String(120), nullable=False)
    recipient_name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="ZAR")
    status = db.Column(
        db.String(30),
        nullable=False,
        default=TransactionStatus.PENDING_VERIFICATION.value,
    )
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    def __repr__(self):
        return f"<Transaction {self.reference} {self.status}>"
