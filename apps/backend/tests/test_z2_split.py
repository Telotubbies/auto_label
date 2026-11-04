"""Z2: the backend hot files are split per feature and the split modules stay wired.

Each test fails when a domain module is added but not re-exported or registered, which is the
regression these splits exist to prevent.
"""
from app import models
from app.db import Base


def test_every_model_class_is_reexported():
    """``from app.models import X`` must keep working after the per-domain split."""
    missing = []
    for module in models.DOMAIN_MODULES:
        for name, obj in vars(module).items():
            if isinstance(obj, type) and issubclass(obj, Base) and obj is not Base:
                if getattr(models, name, None) is not obj:
                    missing.append(f"{module.__name__}.{name}")
    assert not missing, f"model classes not re-exported by app.models: {missing}"


def test_every_upgraded_table_exists_in_the_schema():
    """A per-domain column block naming a table the schema lacks would only fail at boot."""
    from app.schema import STEPS
    missing = [table for table, _ in STEPS if table not in Base.metadata.tables]
    assert not missing, f"column upgrades for unknown tables: {missing}"


def test_bootstrap_still_exposes_ensure_columns():
    """The column helper moved to app.schema; app.bootstrap must keep re-exporting it."""
    from app import bootstrap, schema
    assert bootstrap.ensure_columns is schema.ensure_columns


def test_worker_registry_is_the_union_of_the_feature_modules():
    """``worker.HANDLERS`` must be composed from app.handlers, not maintained beside it."""
    from app import worker
    from app.handlers import MODULES

    expected = {}
    for module in MODULES:
        expected.update(module.HANDLERS)
    assert worker.HANDLERS == expected


def test_handlers_are_defined_in_their_feature_module():
    """The runner keeps the queue and the watchdogs; the job bodies live in app.handlers.*."""
    from app import worker

    assert worker.run_version.__module__ == "app.handlers.versioning"
    assert worker.run_export_engine.__module__ == "app.handlers.versioning"
    assert worker.run_train.__module__ == "app.handlers.training"
    assert worker.run_extract_frames.__module__ == "app.handlers.streams"
    assert worker.run_insights_images.__module__ == "app.handlers.insights"
    assert worker.run_retention.__module__ == "app.handlers.ops"
