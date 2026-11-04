"""The test environment must not depend on which module imported ``app`` first (I15).

``mailer.INBOX_ENABLED`` is computed once at import from ``LD_MAIL_DEV`` and
``LD_PUBLIC_URL``; ``config.SEED_DEMO`` is read at import too. If only the module that needs
the inbox pins those variables, a mixed pytest selection freezes the wrong values for every
later module. ``conftest.py`` therefore pins them before any ``app`` import.
"""
import os


def test_environment_is_pinned_before_app_import():
    from app import config, mailer

    assert config.ENVIRONMENT == "dev"
    assert config.PUBLIC_URL == "http://localhost:5173"
    assert config.SEED_DEMO is True
    assert os.environ.get("LD_MAIL_DEV") == "1"
    assert mailer.INBOX_ENABLED is True


def test_production_environment_values_do_not_leak_into_tests():
    # A developer's exported shell values must not change what this suite proves.
    from app import config

    assert config.ENVIRONMENT != "production"
    assert config.SEED_DEMO is True
