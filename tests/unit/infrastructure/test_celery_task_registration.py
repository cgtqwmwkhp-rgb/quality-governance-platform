"""Ensure Celery workers load real application tasks (not an empty registry)."""

from __future__ import annotations

import os

import pytest

# celery_app imports settings at module load; keep local/dev defaults safe.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/quality_governance",
)


@pytest.fixture(scope="module")
def celery_app_module():
    from src.infrastructure.tasks.celery_app import CELERY_TASK_MODULES, celery_app

    # Force the same import path the worker uses via include/imports.
    celery_app.loader.import_default_modules()
    return celery_app, CELERY_TASK_MODULES


def test_celery_include_lists_task_modules(celery_app_module):
    celery_app, modules = celery_app_module
    assert modules
    assert set(celery_app.conf.include) == set(modules)
    assert set(celery_app.conf.imports) == set(modules)


def test_send_email_and_monitor_tasks_are_registered(celery_app_module):
    celery_app, _ = celery_app_module
    registered = set(celery_app.tasks.keys())

    assert "src.infrastructure.tasks.email_tasks.send_email" in registered
    assert "src.infrastructure.tasks.monitor_tasks.log_task_queue_depth" in registered
    assert "src.infrastructure.tasks.cleanup_tasks.cleanup_expired_tokens" in registered
    assert "src.infrastructure.tasks.webhook_tasks.deliver_webhook" in registered
    assert "src.infrastructure.tasks.safety_asset_expiry_tasks.check_safety_asset_expiry" in registered

    app_tasks = [name for name in registered if name.startswith("src.infrastructure.tasks.")]
    assert len(app_tasks) >= 10
