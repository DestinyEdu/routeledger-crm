import os
import secrets
import uuid
from datetime import timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import click
from flask import Flask, redirect, render_template, request, session, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import Transaction, TransactionStatus, User, db

STATUS_FLOW = [s.value for s in TransactionStatus]
FUNDED_STATUSES = [
    TransactionStatus.VERIFIED.value,
    TransactionStatus.AWAITING_PAYOUT.value,
    TransactionStatus.COMPLETED.value,
]
MAX_AMOUNT = Decimal("10000000000")
MIN_PASSWORD_LENGTH = 12

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.login_message = None
login_manager.session_protection = "strong"

# Compared against when a username doesn't exist, so response time doesn't
# reveal which usernames are real.
DUMMY_HASH = generate_password_hash("not-a-real-password")


def load_secret_key(app):
    key = os.environ.get("ROUTELEDGER_SECRET_KEY")
    if key:
        return key
    os.makedirs(app.instance_path, exist_ok=True)
    path = os.path.join(app.instance_path, "secret_key")
    if not os.path.exists(path):
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(32))
    with open(path) as f:
        return f.read().strip()


def safe_next(target):
    """Only allow redirects to paths on this site (blocks open redirects)."""
    if (
        target
        and target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
    ):
        return target
    return url_for("dashboard")


def create_app(test_config=None):
    app = Flask(__name__)
    if test_config and test_config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = test_config["SECRET_KEY"]
    else:
        app.config["SECRET_KEY"] = load_secret_key(app)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///routeledger.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["WTF_CSRF_TIME_LIMIT"] = None  # token lasts for the session
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    @app.template_filter("local_time")
    def local_time(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        local = value.astimezone(ZoneInfo("Africa/Johannesburg"))
        return local.strftime("%Y-%m-%d %H:%M")

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

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        next_url = request.values.get("next", "")
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user:
                valid = user.check_password(password)
            else:
                check_password_hash(DUMMY_HASH, password)
                valid = False

            if valid:
                session.clear()  # fresh session on login
                login_user(user)
                return redirect(safe_next(next_url))
            return (
                render_template(
                    "login.html",
                    error="Invalid username or password.",
                    next_url=next_url,
                ),
                401,
            )
        return render_template("login.html", error=None, next_url=next_url)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        return render_dashboard()

    @app.route("/transactions", methods=["POST"])
    @login_required
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
    @login_required
    def advance_transaction(transaction_id):
        tx = db.get_or_404(Transaction, transaction_id)
        position = STATUS_FLOW.index(tx.status)
        if position < len(STATUS_FLOW) - 1:
            tx.status = STATUS_FLOW[position + 1]
            db.session.commit()
        return redirect(url_for("dashboard"))

    @app.cli.command("create-user")
    @click.argument("username")
    @click.password_option()
    def create_user(username, password):
        """Create a login: flask --app run create-user NAME"""
        username = username.strip().lower()
        if not username or len(username) > 64:
            raise click.ClickException("Username must be 1-64 characters.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
        if User.query.filter_by(username=username).first():
            raise click.ClickException("That username already exists.")
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created user '{username}'.")

    return app
