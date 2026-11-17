"""The one way to a logged-in client in the backend suite (T-056).

A module that copied its own fifteen-line login helper is the defect this file guards: the
shared `conftest.login` must authenticate through the real route, must raise instead of
returning empty headers when the seed is broken, and must reach a second account.
"""

import pytest
from fastapi.testclient import TestClient

from app.bootstrap import DEMO_EMAIL
from app.main import app
from conftest import login, login_as

PROTECTED = "/api/me"


def test_login_returns_authorization_headers():
    with TestClient(app) as c:
        headers = login(c)
        assert list(headers) == ["Authorization"]
        assert headers["Authorization"].startswith("Bearer ")
        # the headers are real: a protected route answers 200, not 401
        r = c.get(PROTECTED, headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["email"] == DEMO_EMAIL


def test_login_raises_on_a_wrong_password():
    with TestClient(app) as c:
        with pytest.raises(RuntimeError, match="login failed"):
            login(c, DEMO_EMAIL, "not-the-demo-password")


def test_login_as_reaches_a_second_account():
    with TestClient(app) as c:
        admin = c.get(PROTECTED, headers=login(c)).json()
        labeler = c.get(PROTECTED, headers=login_as(c, "labeler@labeldesk.dev"))
        assert labeler.status_code == 200, labeler.text
        assert labeler.json()["email"] == "labeler@labeldesk.dev"
        assert labeler.json()["id"] != admin["id"]
