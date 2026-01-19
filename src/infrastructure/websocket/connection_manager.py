"""
WebSocket Connection Manager - Real-Time Communication Infrastructure

Features:
- Multi-connection per user support
- Channel-based subscriptions
- Presence tracking (online/offline)
- Heartbeat/ping-pong
- Graceful reconnection handling
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class UserConnection:
    """Represents a single WebSocket connection for a user"""

    websocket: WebSocket
    user_id: int
    connection_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    subscribed_channels: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PresenceInfo:
    """User presence information"""

    user_id: int
    status: str  # 'online', 'away', 'busy', 'offline'
    last_seen: datetime
    active_connections: int
    current_page: Optional[str] = None


class ConnectionManager:
    """
    Manages WebSocket connections for real-time features.

    Features:
    - Multiple connections per user (different tabs/devices)
    - Channel subscriptions for topic-based messaging
    - Presence tracking with heartbeats
    - Broadcast to users, channels, or all
    """

    def __init__(self):
        # user_id -> list of connections
        self.user_connections: Dict[int, List[UserConnection]] = {}

        # channel_name -> set of user_ids
        self.channels: Dict[str, Set[int]] = {}

        # user_id -> PresenceInfo
        self.presence: Dict[int, PresenceInfo] = {}

        # Event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}

        # Connection counter for unique IDs
        self._connection_counter = 0

        # Heartbeat interval (seconds)
        self.heartbeat_interval = 30

        # Presence timeout (seconds)
        self.presence_timeout = 60

    def _generate_connection_id(self) -> str:
        """Generate unique connection ID"""
        self._connection_counter += 1
        return f"conn_{self._connection_counter}_{datetime.utcnow().timestamp()}"

    async def connect(
        self, websocket: WebSocket, user_id: int, metadata: Optional[Dict[str, Any]] = None
    ) -> UserConnection:
        """
        Accept a new WebSocket connection for a user.

        Args:
            websocket: The WebSocket connection
            user_id: The authenticated user's ID
            metadata: Optional connection metadata (device, page, etc.)

        Returns:
            UserConnection object
        """
        await websocket.accept()

        connection_id = self._generate_connection_id()
        connection = UserConnection(
            websocket=websocket, user_id=user_id, connection_id=connection_id, metadata=metadata or {}
        )

        # Add to user's connections
        if user_id not in self.user_connections:
            self.user_connections[user_id] = []
        self.user_connections[user_id].append(connection)

        # Update presence
        self._update_presence(user_id, "online")

        # Auto-subscribe to user's personal channel
        await self.subscribe_to_channel(connection, f"user_{user_id}")

        logger.info(f"User {user_id} connected (connection_id={connection_id})")

        # Trigger connection event
        await self._trigger_event("connect", {"user_id": user_id, "connection_id": connection_id})

        return connection

    async def disconnect(self, connection: UserConnection):
        """
        Handle WebSocket disconnection.

        Args:
            connection: The connection to remove
        """
        user_id = connection.user_id

        # Remove from user's connections
        if user_id in self.user_connections:
            self.user_connections[user_id] = [
                c for c in self.user_connections[user_id] if c.connection_id != connection.connection_id
            ]

            # Clean up empty user entry
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
                self._update_presence(user_id, "offline")

        # Remove from all channels
        for channel in list(connection.subscribed_channels):
            await self.unsubscribe_from_channel(connection, channel)

        logger.info(f"User {user_id} disconnected (connection_id={connection.connection_id})")

        # Trigger disconnect event
        await self._trigger_event("disconnect", {"user_id": user_id, "connection_id": connection.connection_id})

    async def subscribe_to_channel(self, connection: UserConnection, channel: str):
        """Subscribe a connection to a channel"""
        if channel not in self.channels:
            self.channels[channel] = set()

        self.channels[channel].add(connection.user_id)
        connection.subscribed_channels.add(channel)

        logger.debug(f"User {connection.user_id} subscribed to channel: {channel}")

    async def unsubscribe_from_channel(self, connection: UserConnection, channel: str):
        """Unsubscribe a connection from a channel"""
        if channel in self.channels:
            self.channels[channel].discard(connection.user_id)

            # Clean up empty channel
            if not self.channels[channel]:
                del self.channels[channel]

        connection.subscribed_channels.discard(channel)

        logger.debug(f"User {connection.user_id} unsubscribed from channel: {channel}")

    async def send_to_user(self, user_id: int, message: Dict[str, Any], event_type: str = "notification") -> int:
        """
        Send a message to all connections of a specific user.

        Args:
            user_id: Target user ID
            message: Message payload
            event_type: Event type for the message

        Returns:
            Number of connections message was sent to
        """
        if user_id not in self.user_connections:
            return 0

        payload = json.dumps({"type": event_type, "data": message, "timestamp": datetime.utcnow().isoformat()})

        sent_count = 0
        failed_connections = []

        for connection in self.user_connections[user_id]:
            try:
                await connection.websocket.send_text(payload)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to user {user_id}: {e}")
                failed_connections.append(connection)

        # Clean up failed connections
        for connection in failed_connections:
            await self.disconnect(connection)

        return sent_count

    async def broadcast_to_channel(
        self,
        channel: str,
        message: Dict[str, Any],
        event_type: str = "channel_message",
        exclude_user_ids: Optional[Set[int]] = None,
    ) -> int:
        """
        Broadcast a message to all users subscribed to a channel.

        Args:
            channel: Target channel name
            message: Message payload
            event_type: Event type for the message
            exclude_user_ids: Users to exclude from broadcast

        Returns:
            Number of users message was sent to
        """
        if channel not in self.channels:
            return 0

        exclude_user_ids = exclude_user_ids or set()
        sent_count = 0

        for user_id in self.channels[channel]:
            if user_id not in exclude_user_ids:
                count = await self.send_to_user(user_id, message, event_type)
                if count > 0:
                    sent_count += 1

        return sent_count

    async def broadcast_to_all(self, message: Dict[str, Any], event_type: str = "broadcast") -> int:
        """
        Broadcast a message to all connected users.

        Args:
            message: Message payload
            event_type: Event type for the message

        Returns:
            Number of users message was sent to
        """
        sent_count = 0

        for user_id in list(self.user_connections.keys()):
            count = await self.send_to_user(user_id, message, event_type)
            if count > 0:
                sent_count += 1

        return sent_count

    def _update_presence(self, user_id: int, status: str):
        """Update user's presence status"""
        connection_count = len(self.user_connections.get(user_id, []))

        self.presence[user_id] = PresenceInfo(
            user_id=user_id,
            status=status if connection_count > 0 else "offline",
            last_seen=datetime.utcnow(),
            active_connections=connection_count,
        )

    def get_presence(self, user_id: int) -> Optional[PresenceInfo]:
        """Get a user's presence information"""
        return self.presence.get(user_id)

    def get_online_users(self) -> List[int]:
        """Get list of all online user IDs"""
        return [user_id for user_id, presence in self.presence.items() if presence.status == "online"]

    def is_user_online(self, user_id: int) -> bool:
        """Check if a user is currently online"""
        presence = self.presence.get(user_id)
        return presence is not None and presence.status == "online"

    async def handle_heartbeat(self, connection: UserConnection) -> None:
        """Handle heartbeat/ping from client"""
        connection.last_ping = datetime.utcnow()
        self._update_presence(connection.user_id, "online")

        # Send pong response
        try:
            await connection.websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
        except Exception:
            pass
        return None

    def register_event_handler(self, event: str, handler: Callable):
        """Register a handler for WebSocket events"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)

    async def _trigger_event(self, event: str, data: Dict[str, Any]):
        """Trigger registered event handlers"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(data)
                    else:
                        handler(data)
                except Exception as e:
                    logger.error(f"Event handler error for {event}: {e}")

    async def handle_message(self, connection: UserConnection, message: str) -> Optional[Dict[str, Any]]:
        """
        Handle incoming WebSocket message from client.

        Args:
            connection: The connection that sent the message
            message: Raw message string

        Returns:
            Response to send back, or None
        """
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "ping":
                await self.handle_heartbeat(connection)
                return None

            elif msg_type == "subscribe":
                channel = data.get("channel")
                if channel:
                    await self.subscribe_to_channel(connection, channel)
                    return {"type": "subscribed", "channel": channel}
                return None

            elif msg_type == "unsubscribe":
                channel = data.get("channel")
                if channel:
                    await self.unsubscribe_from_channel(connection, channel)
                    return {"type": "unsubscribed", "channel": channel}
                return None

            elif msg_type == "presence":
                status = data.get("status", "online")
                page = data.get("page")
                self._update_presence(connection.user_id, status)
                if page:
                    presence = self.presence.get(connection.user_id)
                    if presence:
                        presence.current_page = page
                return None

            else:
                # Trigger custom message handler
                await self._trigger_event("message", {"connection": connection, "type": msg_type, "data": data})
                return None

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from user {connection.user_id}")
            return {"type": "error", "message": "Invalid JSON"}
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"type": "error", "message": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_users": len(self.user_connections),
            "total_connections": sum(len(conns) for conns in self.user_connections.values()),
            "total_channels": len(self.channels),
            "online_users": len(self.get_online_users()),
            "channels": {name: len(users) for name, users in self.channels.items()},
        }


# Global connection manager instance
connection_manager = ConnectionManager()
