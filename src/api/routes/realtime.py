"""Real-Time WebSocket API routes.

Thin controller layer — broadcast / stats / presence logic lives in RealtimeService.
WebSocket lifecycle stays here as it is a transport concern.
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from src.api.dependencies import CurrentUser, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.core.security import decode_token, is_token_revoked
from src.domain.exceptions import AuthorizationError
from src.domain.models.user import User
from src.domain.services.realtime_service import RealtimeService
from src.infrastructure.websocket.connection_manager import connection_manager

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionStats(BaseModel):
    total_users: int
    total_connections: int
    total_channels: int
    online_users: int


class PresenceResponse(BaseModel):
    user_id: int
    status: str
    last_seen: str
    active_connections: int


class OnlineUsersResponse(BaseModel):
    online_users: list[int]
    count: int


class BroadcastResponse(BaseModel):
    success: bool
    recipients: int
    channel: Optional[str] = None


class BroadcastMessageRequest(BaseModel):
    message_type: str = "info"
    title: Optional[str] = None
    content: str
    data: Optional[dict] = None


@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int, token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time communication."""
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    try:
        payload = decode_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return

        jti = payload.get("jti")
        if not jti:
            await websocket.close(code=4001, reason="Invalid token: missing jti")
            return

        from src.infrastructure.database import get_db

        async for db in get_db():
            if await is_token_revoked(jti, db):
                await websocket.close(code=4001, reason="Token has been revoked")
                return

        token_user_id = payload.get("sub")
        if token_user_id is not None and int(token_user_id) != user_id:
            await websocket.close(code=4003, reason="User ID mismatch")
            return
    except (WebSocketDisconnect, ConnectionError):
        await websocket.close(code=4001, reason="Token validation failed")
        return

    connection = await connection_manager.connect(websocket=websocket, user_id=user_id, metadata={"token": token})

    try:
        while True:
            message = await websocket.receive_text()
            response = await connection_manager.handle_message(connection, message)
            if response:
                await websocket.send_json(response)
    except WebSocketDisconnect:
        await connection_manager.disconnect(connection)
    except (WebSocketDisconnect, ConnectionError) as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        await connection_manager.disconnect(connection)


@router.get("/stats", response_model=ConnectionStats)
async def get_connection_stats(current_user: CurrentUser):
    """Get WebSocket connection statistics."""
    service = RealtimeService()
    return service.get_stats()


@router.get("/online-users", response_model=OnlineUsersResponse)
async def get_online_users(current_user: CurrentUser):
    """Get list of currently online user IDs."""
    service = RealtimeService()
    return service.get_online_users()


@router.get("/presence/{user_id}", response_model=Optional[PresenceResponse])
async def get_user_presence(user_id: int, current_user: CurrentUser):
    """Get presence information for a specific user."""
    service = RealtimeService()
    return service.get_presence(user_id)


@router.post("/broadcast", response_model=BroadcastResponse)
async def broadcast_message(
    message: BroadcastMessageRequest,
    current_user: Annotated[User, Depends(require_permission("realtime:create"))],
    channel: Optional[str] = None,
):
    """Broadcast a message to connected users. Admin only."""
    if not current_user.is_superuser:
        raise AuthorizationError(ErrorCode.PERMISSION_DENIED)

    service = RealtimeService()
    return await service.broadcast(message.model_dump(), channel=channel)
