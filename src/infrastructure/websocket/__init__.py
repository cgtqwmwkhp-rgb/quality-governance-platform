"""WebSocket infrastructure for real-time communication."""

from src.infrastructure.websocket.connection_manager import (
    ConnectionManager,
    PresenceInfo,
    UserConnection,
    connection_manager,
)

__all__ = [
    "ConnectionManager",
    "UserConnection",
    "PresenceInfo",
    "connection_manager",
]
