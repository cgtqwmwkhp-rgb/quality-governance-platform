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

import logging
from typing import Any

from celery.signals import worker_init, worker_process_init, worker_ready

from src.infrastructure.database import configure_celery_worker_database

logger = logging.getLogger(__name__)


@worker_init.connect
def _configure_worker_main_process(**_kwargs: Any) -> None:
    """Runs once in the worker's main process, before any pool type forks."""
    configure_celery_worker_database()


@worker_process_init.connect
def _configure_worker_child_process(**_kwargs: Any) -> None:
    """Runs in each prefork child; also resets pools inherited across ``fork``."""
    configure_celery_worker_database()


@worker_ready.connect
def _log_engine_pool(**_kwargs: Any) -> None:
    """State the live pool class once the worker can actually log it.

    The rebind's own log record never reaches the container log: Celery sends
    ``worker_init`` (celery/worker/worker.py) before ``on_init_blueprint`` calls
    ``setup_logging``, so the record goes to a root logger still at WARNING, and
    prefork children return early from the idempotent rebind without reaching the
    log call. That left no way to confirm the fix from logs alone.

    Warn rather than inform when the pool is wrong: a pooled worker engine is the
    precondition for the cross-event-loop failure this module exists to prevent.
    """
    from sqlalchemy.pool import NullPool

    from src.infrastructure import database

    pool_name = type(database.engine.pool).__name__
    if isinstance(database.engine.pool, NullPool):
        logger.info("Celery worker async engine pool: %s (connection per task)", pool_name)
    else:
        logger.warning(
            "Celery worker async engine pool is %s, expected NullPool — tasks after the "
            "first in each process may fail with 'attached to a different loop'",
            pool_name,
        )
