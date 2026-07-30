"""Web Push subscription and notification delivery log models.

These previously lived in ``src/api/routes/push_notifications.py``, which meant
``alembic/env.py`` never imported them and the drift gate could not see the
tables (C-67). They belong with the rest of the domain metadata.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text

from src.domain.models.base import Base


class PushSubscription(Base):
    """Web Push subscription storage."""

    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)  # Null for anonymous
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh_key = Column(String(255), nullable=False)
    auth_key = Column(String(255), nullable=False)
    user_agent = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_used_at = Column(DateTime, nullable=True)


class NotificationLog(Base):
    """Log of sent notifications."""

    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    subscription_id = Column(Integer, nullable=True)

    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    data = Column(JSON, nullable=True)

    channel = Column(String(20), nullable=False)  # push, email, sms
    status = Column(String(20), default="pending")  # pending, sent, failed, delivered
    error_message = Column(Text, nullable=True)

    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
