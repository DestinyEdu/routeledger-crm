import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app.models import AuditLog, db

WINDOW = timedelta(minutes=15)
MAX_FAILURES_PER_IP_AND_USER = 5
MAX_FAILURES_PER_IP = 20


def _aware(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _lockout_seconds(query, limit, now):
    """Seconds until fewer than `limit` failures remain in the window (0 = open)."""
    times = [
        _aware(row.created_at)
        for row in query.order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()
    ]
    if len(times) < limit:
        return 0
    unlock_at = times[len(times) - limit] + WINDOW
    return max(0, math.ceil((unlock_at - now).total_seconds()))


def login_lockout_seconds(ip, username):
    """How long this IP/username must wait before another login attempt (0 = allowed)."""
    if not ip:
        return 0
    now = datetime.now(timezone.utc)
    since = now - WINDOW

    ip_failures = AuditLog.query.filter(
        AuditLog.action == "auth.login_failed",
        AuditLog.ip_address == ip,
        AuditLog.created_at >= since,
    )

    # A successful login resets the counter for this IP + username
    last_ok = (
        db.session.query(func.max(AuditLog.created_at))
        .filter(
            AuditLog.action == "auth.login",
            AuditLog.ip_address == ip,
            AuditLog.username == username,
        )
        .scalar()
    )
    user_failures = ip_failures.filter(AuditLog.username == username)
    if last_ok is not None:
        user_failures = user_failures.filter(AuditLog.created_at > last_ok)

    return max(
        _lockout_seconds(ip_failures, MAX_FAILURES_PER_IP, now),
        _lockout_seconds(user_failures, MAX_FAILURES_PER_IP_AND_USER, now),
    )


def already_logged_block(ip, username):
    """True if a 'blocked' event was already recorded in this window."""
    since = datetime.now(timezone.utc) - WINDOW
    return (
        AuditLog.query.filter(
            AuditLog.action == "auth.login_blocked",
            AuditLog.ip_address == ip,
            AuditLog.username == username[:64],
            AuditLog.created_at >= since,
        ).first()
        is not None
    )
