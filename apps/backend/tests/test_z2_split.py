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
