"""Tests for Celery task configuration."""

import pytest


class TestCeleryConfiguration:
    """Tests for Celery app configuration."""

    def test_celery_app_imports(self):
        """Test Celery app can be imported."""
        from src.infrastructure.tasks.celery_app import celery_app

        assert celery_app is not None
        assert celery_app.main == "quality_governance"

    def test_celery_queues_configured(self):
        """Test expected queues are configured."""
        from src.infrastructure.tasks.celery_app import celery_app

        queues = celery_app.conf.task_queues
        if isinstance(queues, dict):
            queue_names = set(queues.keys())
        else:
            queue_names = {q.name if hasattr(q, "name") else str(q) for q in queues}
        expected = {"default", "email", "notifications", "reports", "cleanup"}
        assert expected.issubset(queue_names)

    def test_beat_schedule_configured(self):
        """Test beat schedule has expected tasks."""
        from src.infrastructure.tasks.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert len(schedule) >= 3

    def test_email_task_registered(self):
        """Test email task module can be imported."""
        from src.infrastructure.tasks.email_tasks import send_email

        assert send_email is not None

    def test_cleanup_task_registered(self):
        """Test cleanup task module can be imported."""
        from src.infrastructure.tasks.cleanup_tasks import cleanup_expired_tokens

        assert cleanup_expired_tokens is not None

    def test_notification_task_registered(self):
        """Test notification task module can be imported."""
        from src.infrastructure.tasks.notification_tasks import send_push_notification

        assert send_push_notification is not None
