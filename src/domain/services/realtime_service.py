"""Real-time / WebSocket domain service.

Extracts broadcast and presence logic from the realtime route module.
WebSocket connection lifecycle stays in the route (transport concern).
"""

import logging
from typing import Any, Optional

from src.infrastructure.monitoring.azure_monitor import track_metric
from src.infrastructure.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)


class RealtimeService:
    """Wraps the connection manager for broadcast, stats, and presence queries."""

    def get_stats(self) -> dict[str, Any]:
        track_metric("realtime.connections", 1)
        stats = connection_manager.get_stats()
        return {
            "total_users": stats["total_users"],
            "total_connections": stats["total_connections"],
            "total_channels": stats["total_channels"],
            "online_users": stats["online_users"],
        }

    def get_online_users(self) -> dict[str, Any]:
        online = connection_manager.get_online_users()
        return {"online_users": online, "count": len(online)}

    def get_presence(self, user_id: int) -> Optional[dict[str, Any]]:
        presence = connection_manager.get_presence(user_id)
        if presence:
            return {
                "user_id": presence.user_id,
                "status": presence.status,
                "last_seen": presence.last_seen.isoformat(),
                "active_connections": presence.active_connections,
            }
        return None

    async def broadcast(
        self,
        message: dict[str, Any],
        *,
        channel: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast a message to all users or to a specific channel.

        Returns:
            Dict with success flag, recipient count, and optional channel.
        """
        if channel:
            count = await connection_manager.broadcast_to_channel(
                channel=channel,
                message=message,
                event_type="admin_broadcast",
            )
        else:
            count = await connection_manager.broadcast_to_all(
                message=message,
                event_type="admin_broadcast",
            )

        return {"success": True, "recipients": count, "channel": channel}
