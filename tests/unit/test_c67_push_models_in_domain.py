"""C-67: push notification ORM models must be visible to alembic metadata."""

from __future__ import annotations


def test_push_tables_register_without_importing_api_routes():
    """Importing the domain module alone must put both tables on Base.metadata.

    Before C-67 the models lived in ``src.api.routes.push_notifications``, which
    ``alembic/env.py`` never imports, so the drift gate could not see them.
    """
    import importlib
    import sys

    # Drop any prior route import so this test cannot pass via residual registration.
    for name in list(sys.modules):
        if name.startswith("src.api.routes.push_notifications"):
            del sys.modules[name]

    importlib.import_module("src.domain.models.push_notification")
    from src.domain.models.base import Base

    assert "push_subscriptions" in Base.metadata.tables
    assert "notification_logs" in Base.metadata.tables


def test_push_notification_module_is_on_alembic_env_side_effect_list():
    from scripts.ops.run025._models import side_effect_model_modules

    assert "src.domain.models.push_notification" in side_effect_model_modules()
