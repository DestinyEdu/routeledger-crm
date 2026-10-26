from datetime import datetime, timedelta, timezone

from app.models import AuditLog, db

IP = "10.1.1.1"
OTHER_IP = "10.2.2.2"


def attempt(client, username, password, ip=IP):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        environ_base={"REMOTE_ADDR": ip},
    )


def fail(client, username="tester", times=1, ip=IP):
    for _ in range(times):
        assert attempt(client, username, "wrong-password-123", ip).status_code == 401


def seed_failures(app, count, username="tester", ip=IP, age=timedelta(0)):
    with app.app_context():
        for i in range(count):
            db.session.add(
                AuditLog(
                    action="auth.login_failed",
                    username=username if username else f"user{i}",
                    ip_address=ip,
                    created_at=datetime.now(timezone.utc) - age,
                )
            )
        db.session.commit()


def blocked_count(app):
    with app.app_context():
        return AuditLog.query.filter_by(action="auth.login_blocked").count()


def test_fifth_failure_locks_even_the_correct_password(app, client, user):
    fail(client, times=5)
    resp = attempt(client, user["username"], user["password"])
    assert resp.status_code == 429
    assert "Too many failed sign-in attempts" in resp.get_data(as_text=True)
    assert 0 < int(resp.headers["Retry-After"]) <= 15 * 60
    assert client.get("/").status_code == 302  # not signed in


def test_four_failures_do_not_lock(client, user):
    fail(client, times=4)
    resp = attempt(client, user["username"], user["password"])
    assert resp.status_code == 302


def test_unknown_usernames_are_throttled_the_same_way(client, user):
    fail(client, username="nobody", times=5)
    resp = attempt(client, "nobody", "wrong-password-123")
    assert resp.status_code == 429


def test_lock_is_per_ip_and_username(app, client, user):
    seed_failures(app, 5, username="tester", ip=IP)
    # Same user from another IP: fine
    assert attempt(client, user["username"], user["password"], ip=OTHER_IP).status_code == 302
    # Another username from the locked IP: not locked
    other = app.test_client()
    assert attempt(other, "someone-else", "wrong-password-123").status_code == 401


def test_ip_wide_limit(app, client, user):
    seed_failures(app, 20, username="", ip=IP)  # 20 different usernames
    resp = attempt(client, user["username"], user["password"])
    assert resp.status_code == 429


def test_old_failures_expire(app, client, user):
    seed_failures(app, 5, age=timedelta(minutes=16))
    resp = attempt(client, user["username"], user["password"])
    assert resp.status_code == 302


def test_lock_lifts_when_oldest_failures_age_out(app, client, user):
    seed_failures(app, 5, age=timedelta(minutes=14))
    resp = attempt(client, user["username"], user["password"])
    assert resp.status_code == 429
    assert 0 < int(resp.headers["Retry-After"]) <= 61


def test_successful_login_resets_the_counter(app, client, user):
    fail(client, times=4)
    assert attempt(client, user["username"], user["password"]).status_code == 302

    fresh = app.test_client()  # new browser session
    fail(fresh, times=4)
    # 8 failures in total, but only 4 since the last success
    assert attempt(fresh, user["username"], user["password"]).status_code == 302


def test_blocked_attempts_are_logged_once(app, client, user):
    fail(client, times=5)
    for _ in range(4):
        assert attempt(client, user["username"], user["password"]).status_code == 429
    assert blocked_count(app) == 1
