"""C4: ciphertext and long audit targets must fit their columns on Postgres."""
from sqlalchemy import Text

from app.models import Audit, Webhook


def test_webhook_secret_column_is_unbounded_text():
    assert isinstance(Webhook.__table__.c.secret.type, Text)


def test_audit_target_is_unbounded_text():
    assert isinstance(Audit.__table__.c.target.type, Text)


def test_webhook_secret_round_trips_a_real_ciphertext():
    from app.services import secretbox
    token = secretbox.encrypt("whsec_" + "a" * 32)
    assert len(token) > 64
    assert Webhook(workspace_id="w", url="https://example.com", secret=token).secret == token


def test_postgres_widening_runs_for_existing_columns(monkeypatch):
    """The upgrade path must ALTER an existing schema, not only create new tables."""
    from app import bootstrap

    calls = []

    class FakeConn:
        def exec_driver_sql(self, sql):
            calls.append(sql)

    class FakeBegin:
        def __enter__(self):
            return FakeConn()

        def __exit__(self, *exc):
            return False

    class FakeEngine:
        dialect = type("D", (), {"name": "postgresql"})()

        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(bootstrap, "engine", FakeEngine())
    bootstrap._widen_text_columns()
    joined = " ".join(calls).lower()
    assert "webhooks" in joined and "secret" in joined and "text" in joined
    assert "audit" in joined and "target" in joined
