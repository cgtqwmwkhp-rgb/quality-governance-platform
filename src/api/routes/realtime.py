"""
Real-Time WebSocket API Routes

Features:
- WebSocket connection handling
- Real-time notifications
- Presence tracking
- Channel subscriptions
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from src.api.dependencies import CurrentUser
from src.core.security import decode_token, is_token_revoked
from src.infrastructure.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionStats(BaseModel):
    """WebSocket connection statistics"""

    total_users: int
    total_connections: int
    total_channels: int
    online_users: int


class PresenceResponse(BaseModel):
    """User presence response"""

    user_id: int
    status: str
    last_seen: str
    active_connections: int


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: Optional[str] = Query(None)):
    """
    WebSocket endpoint for real-time communication.

    Connect with: ws://host/api/v1/realtime/ws/{user_id}?token=JWT_TOKEN

    Message Protocol:

    Client -> Server:
    - { "type": "ping" } - Heartbeat
    - { "type": "subscribe", "channel": "channel_name" } - Subscribe to channel
    - { "type": "unsubscribe", "channel": "channel_name" } - Unsubscribe
    - { "type": "presence", "status": "online|away|busy", "page": "/current/page" }

    Server -> Client:
    - { "type": "pong", "timestamp": "..." } - Heartbeat response
    - { "type": "notification", "data": {...} } - Notification
    - { "type": "channel_message", "data": {...} } - Channel broadcast
    - { "type": "presence_update", "data": {...} } - Presence change
    """

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return

        jti = payload.get("jti")
        if jti:
            from src.infrastructure.database import get_db

            async for db in get_db():
                if await is_token_revoked(jti, db):
                    await websocket.close(code=4001, reason="Token has been revoked")
                    return

        token_user_id = payload.get("sub")
        if token_user_id is not None and int(token_user_id) != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except Exception:
        await websocket.close(code=4001, reason="Token validation failed")
        return

    connection = await connection_manager.connect(websocket=websocket, user_id=user_id, metadata={"token": token})

    try:
        while True:
            # Receive message from client
            message = await websocket.receive_text()

            # Handle message
            response = await connection_manager.handle_message(connection, message)

            # Send response if any
            if response:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        await connection_manager.disconnect(connection)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await connection_manager.disconnect(connection)


@router.get("/stats", response_model=ConnectionStats)
async def get_connection_stats(current_user: CurrentUser):
    """
    Get WebSocket connection statistics.

    Returns current connection counts and channel information.
    """
    stats = connection_manager.get_stats()
    return ConnectionStats(
        total_users=stats["total_users"],
        total_connections=stats["total_connections"],
        total_channels=stats["total_channels"],
        online_users=stats["online_users"],
    )


@router.get("/online-users")
async def get_online_users(current_user: CurrentUser):
    """
    Get list of currently online user IDs.

    Returns list of user IDs with active WebSocket connections.
    """
    return {
        "online_users": connection_manager.get_online_users(),
        "count": len(connection_manager.get_online_users()),
    }


@router.get("/presence/{user_id}", response_model=Optional[PresenceResponse])
async def get_user_presence(user_id: int, current_user: CurrentUser):
    """
    Get presence information for a specific user.

    Returns:
    - status: 'online', 'away', 'busy', or 'offline'
    - last_seen: Last activity timestamp
    - active_connections: Number of active connections
    """
    presence = connection_manager.get_presence(user_id)

    if presence:
        return PresenceResponse(
            user_id=presence.user_id,
            status=presence.status,
            last_seen=presence.last_seen.isoformat(),
            active_connections=presence.active_connections,
        )

    return None


@router.post("/broadcast")
async def broadcast_message(message: dict, current_user: CurrentUser, channel: Optional[str] = None):
    """
    Broadcast a message to connected users.

    If channel is provided, broadcasts only to that channel.
    Otherwise, broadcasts to all connected users.

    Admin only endpoint.
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    if channel:
        count = await connection_manager.broadcast_to_channel(
            channel=channel, message=message, event_type="admin_broadcast"
        )
    else:
        count = await connection_manager.broadcast_to_all(message=message, event_type="admin_broadcast")

    return {"success": True, "recipients": count, "channel": channel}
