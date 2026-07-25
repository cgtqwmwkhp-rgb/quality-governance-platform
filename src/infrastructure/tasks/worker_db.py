"""Celery worker database bootstrap (not a ``@task`` module — keep explicit).

Task bodies run their async work through ``asyncio.run``, which closes the event
loop it created. The module-level async engine in :mod:`src.infrastructure.database`
is pooled for the FastAPI process, and a pooled asyncpg connection stays bound to
the loop that opened it — so the *second* task in a worker process fails with
``RuntimeError: ... got Future ... attached to a different loop`` and leaks the
server-side backend until ``max_connections`` runs out.

Worker startup signals are the only reliable place to tell "I am a worker" from
"I am the web app importing ``celery_app`` to dispatch": ``src.infrastructure``
imports the database module before ``celery_app`` is even loaded, so an
import-time decision would have to guess from ``sys.argv``.
"""

from typing import Any

from celery.signals import worker_init, worker_process_init

from src.infrastructure.database import configure_celery_worker_database


@worker_init.connect
def _configure_worker_main_process(**_kwargs: Any) -> None:
    """Runs once in the worker's main process, before any pool type forks."""
    configure_celery_worker_database()


@worker_process_init.connect
def _configure_worker_child_process(**_kwargs: Any) -> None:
    """Runs in each prefork child; also resets pools inherited across ``fork``."""
    configure_celery_worker_database()
