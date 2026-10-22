import uuid
from decimal import Decimal, InvalidOperation

from flask import Flask, redirect, render_template, request, url_for
from sqlalchemy import func

from app.models import Transaction, TransactionStatus, db

STATUS_FLOW = [s.value for s in TransactionStatus]
FUNDED_STATUSES = [
    TransactionStatus.VERIFIED.value,
    TransactionStatus.AWAITING_PAYOUT.value,
    TransactionStatus.COMPLETED.value,
]
MAX_AMOUNT = Decimal("10000000000")


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///routeledger.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    with app.app_context():
        db.create_all()

    def count_status(status):
        return Transaction.query.filter_by(status=status.value).count()

    def render_dashboard(error=None, form=None):
        funds_received = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(Transaction.status.in_(FUNDED_STATUSES))
            .scalar()
        )
        transactions = (
            Transaction.query.order_by(Transaction.created_at.desc()).limit(50).all()
        )
        return render_template(
            "index.html",
            funds_received=funds_received,
            pending_count=count_status(TransactionStatus.PENDING_VERIFICATION),
            awaiting_count=count_status(TransactionStatus.AWAITING_PAYOUT),
            completed_count=count_status(TransactionStatus.COMPLETED),
            transactions=transactions,
            error=error,
            form=form or {},
        )

    @app.route("/")
    def dashboard():
        return render_dashboard()

    @app.route("/transactions", methods=["POST"])
    def create_transaction():
        sender = request.form.get("sender_name", "").strip()
        recipient = request.form.get("recipient_name", "").strip()
        raw_amount = request.form.get("amount", "").strip()

        try:
            amount = Decimal(raw_amount)
        except InvalidOperation:
            amount = None

        error = None
        if not sender or not recipient:
            error = "Sender and recipient names are required."
        elif len(sender) > 120 or len(recipient) > 120:
            error = "Names must be 120 characters or fewer."
        elif amount is None or not amount.is_finite() or amount <= 0 or amount >= MAX_AMOUNT:
            error = "Enter a valid amount greater than zero."

        if error:
            return render_dashboard(error=error, form=request.form), 400

        tx = Transaction(
            reference=f"RL-{uuid.uuid4().hex[:8].upper()}",
            sender_name=sender,
            recipient_name=recipient,
            amount=amount.quantize(Decimal("0.01")),
        )
        db.session.add(tx)
        db.session.commit()
        return redirect(url_for("dashboard"))

    @app.route("/transactions/<int:transaction_id>/advance", methods=["POST"])
    def advance_transaction(transaction_id):
        tx = db.get_or_404(Transaction, transaction_id)
        position = STATUS_FLOW.index(tx.status)
        if position < len(STATUS_FLOW) - 1:
            tx.status = STATUS_FLOW[position + 1]
            db.session.commit()
        return redirect(url_for("dashboard"))

    return app
