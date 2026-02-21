"""
AI Copilot API Routes

Interactive conversational AI assistant for QHSE management.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode

router = APIRouter()


# ============================================================================
# Schemas
# ============================================================================


class SessionCreate(BaseModel):
    context_type: Optional[str] = None
    context_id: Optional[str] = None
    context_data: Optional[dict] = None
    current_page: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    title: Optional[str]
    context_type: Optional[str]
    context_id: Optional[str]
    is_active: bool
    created_at: datetime
    last_message_at: Optional[datetime]

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    content_type: str
    action_type: Optional[str]
    action_data: Optional[dict]
    action_result: Optional[dict]
    action_status: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_type: str = Field(..., pattern="^(helpful|inaccurate|inappropriate|other)$")
    feedback_text: Optional[str] = None


class ActionExecute(BaseModel):
    action_name: str
    parameters: dict = {}


class SuggestedAction(BaseModel):
    action: str
    display_name: str
    description: str
    parameters: dict = {}


# ============================================================================
# Session Endpoints
# ============================================================================


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new copilot conversation session."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    tenant_id = current_user.tenant_id
    user_id = current_user.id

    session = await service.create_session(
        tenant_id=tenant_id,
        user_id=user_id,
        context_type=data.context_type,
        context_id=data.context_id,
        context_data=data.context_data,
        current_page=data.current_page,
    )

    return session


@router.get("/sessions/active", response_model=Optional[SessionResponse])
async def get_active_session(db: DbSession, current_user: CurrentUser):
    """Get the user's active session, if any."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    user_id = current_user.id

    session = await service.get_active_session(user_id)
    return session


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: int, db: DbSession, current_user: CurrentUser):
    """Get a session by ID."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)
    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return session


@router.delete("/sessions/{session_id}", response_model=dict)
async def close_session(session_id: int, db: DbSession, current_user: CurrentUser):
    """Close a session."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)
    await service.close_session(session_id)

    return {"status": "closed"}


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=100),
):
    """List user's recent sessions."""
    from src.domain.models.ai_copilot import CopilotSession

    user_id = current_user.id

    stmt = (
        select(CopilotSession)
        .where(CopilotSession.user_id == user_id)
        .order_by(CopilotSession.updated_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    return sessions


# ============================================================================
# Message Endpoints
# ============================================================================


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: int,
    data: MessageCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Send a message and get AI response."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    user_id = current_user.id

    try:
        message = await service.send_message(
            session_id=session_id,
            content=data.content,
            user_id=user_id,
        )
        return message
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    session_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
):
    """Get messages for a session."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)
    messages = await service.get_session_messages(session_id, limit=limit)

    return messages


@router.post("/messages/{message_id}/feedback", response_model=dict)
async def submit_feedback(
    message_id: int,
    data: FeedbackCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Submit feedback on a copilot response."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    tenant_id = current_user.tenant_id
    user_id = current_user.id

    try:
        feedback = await service.submit_feedback(
            message_id=message_id,
            user_id=user_id,
            tenant_id=tenant_id,
            rating=data.rating,
            feedback_type=data.feedback_type,
            feedback_text=data.feedback_text,
        )
        return {"status": "submitted", "feedback_id": feedback.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)


# ============================================================================
# Action Endpoints
# ============================================================================


@router.get("/actions", response_model=list[dict])
async def list_actions(current_user: CurrentUser, category: Optional[str] = None):
    """List available copilot actions."""
    from src.domain.services.copilot_service import COPILOT_ACTIONS

    actions = list(COPILOT_ACTIONS.values())

    if category:
        actions = [a for a in actions if a["category"] == category]

    return actions


@router.post("/actions/execute", response_model=dict)
async def execute_action(
    data: ActionExecute,
    db: DbSession,
    current_user: CurrentUser,
):
    """Execute a copilot action directly."""
    from src.domain.services.copilot_service import COPILOT_ACTIONS

    if data.action_name not in COPILOT_ACTIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    return {
        "status": "executed",
        "action": data.action_name,
        "parameters": data.parameters,
        "result": {"success": True},
    }


@router.get("/actions/suggest", response_model=list[SuggestedAction])
async def suggest_actions(
    current_user: CurrentUser,
    page: Optional[str] = None,
    context_type: Optional[str] = None,
    context_id: Optional[str] = None,
):
    """Get suggested actions for current context."""
    from src.domain.services.copilot_service import COPILOT_ACTIONS

    suggestions = []

    # Context-based suggestions
    if context_type == "incident":
        suggestions.extend(
            [
                SuggestedAction(
                    action="create_action",
                    display_name="Create Corrective Action",
                    description="Create a CAPA for this incident",
                ),
                SuggestedAction(
                    action="search_incidents",
                    display_name="Find Similar Incidents",
                    description="Search for related incidents",
                ),
            ]
        )
    elif context_type == "audit":
        suggestions.extend(
            [
                SuggestedAction(
                    action="create_action",
                    display_name="Create Finding",
                    description="Record an audit finding",
                ),
            ]
        )

    # Page-based suggestions
    if page == "/incidents":
        suggestions.append(
            SuggestedAction(
                action="create_incident",
                display_name="Log New Incident",
                description="Create a new incident report",
            )
        )
    elif page == "/risks":
        suggestions.append(
            SuggestedAction(
                action="get_risk_summary",
                display_name="Risk Summary",
                description="View current risk summary",
            )
        )

    # Default suggestions
    if not suggestions:
        suggestions = [
            SuggestedAction(
                action="explain",
                display_name="Ask a Question",
                description="Ask about compliance, safety, or procedures",
            ),
            SuggestedAction(
                action="navigate",
                display_name="Navigate",
                description="Go to a specific page",
            ),
        ]

    return suggestions


# ============================================================================
# Knowledge Base Endpoints
# ============================================================================


@router.get("/knowledge/search", response_model=list[dict])
async def search_knowledge(
    db: DbSession,
    current_user: CurrentUser,
    query: str = Query(..., min_length=2),
    category: Optional[str] = None,
    limit: int = Query(5, ge=1, le=20),
):
    """Search the copilot knowledge base."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    tenant_id = current_user.tenant_id

    results = await service.search_knowledge(
        query=query,
        tenant_id=tenant_id,
        category=category,
        limit=limit,
    )

    return [
        {
            "id": r.id,
            "title": r.title,
            "content": r.content[:500],
            "category": r.category,
            "tags": r.tags,
        }
        for r in results
    ]


@router.post("/knowledge", response_model=dict)
async def add_knowledge(
    title: str,
    content: str,
    category: str,
    db: DbSession,
    current_user: CurrentUser,
    tags: Optional[list[str]] = None,
):
    """Add to the knowledge base."""
    from src.domain.services.copilot_service import CopilotService

    service = CopilotService(db)

    tenant_id = current_user.tenant_id

    knowledge = await service.add_knowledge(
        title=title,
        content=content,
        category=category,
        tenant_id=tenant_id,
        tags=tags,
    )

    return {"id": knowledge.id, "title": knowledge.title}


# ============================================================================
# WebSocket for Real-time Chat
# ============================================================================


class ConnectionManager:
    """Manage WebSocket connections for real-time chat."""

    def __init__(self):
        self.active_connections: dict[int, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: int):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: int):
        self.active_connections.pop(session_id, None)

    async def send_message(self, message: dict, session_id: int):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: int, token: Optional[str] = Query(None)):
    """WebSocket endpoint for real-time chat."""
    from src.domain.services.copilot_service import CopilotService
    from src.infrastructure.database import get_db

    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return
    try:
        from src.core.security import decode_token, is_token_revoked

        payload = decode_token(token)
        if not payload:
            await websocket.close(code=4001, reason="Invalid token")
            return

        jti = payload.get("jti")
        if jti:
            async for db in get_db():
                if await is_token_revoked(jti, db):
                    await websocket.close(code=4001, reason="Token has been revoked")
                    return

        ws_user_id = int(payload.get("sub", 0))
    except Exception:
        await websocket.close(code=4001, reason="Token validation failed")
        return

    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_json()

            async for db in get_db():
                try:
                    service = CopilotService(db)

                    if data.get("type") == "message":
                        message = await service.send_message(
                            session_id=session_id,
                            content=data["content"],
                            user_id=ws_user_id,
                        )

                        await manager.send_message(
                            {
                                "type": "response",
                                "message": {
                                    "id": message.id,
                                    "role": message.role,
                                    "content": message.content,
                                    "content_type": message.content_type,
                                    "action_type": message.action_type,
                                    "action_data": message.action_data,
                                    "created_at": message.created_at.isoformat(),
                                },
                            },
                            session_id,
                        )

                    elif data.get("type") == "typing":
                        pass

                    elif data.get("type") == "feedback":
                        await service.submit_feedback(
                            message_id=data["message_id"],
                            user_id=ws_user_id,
                            tenant_id=int(payload.get("tenant_id", 0)),
                            rating=data["rating"],
                            feedback_type=data.get("feedback_type", "other"),
                        )

                        await manager.send_message(
                            {"type": "feedback_received"},
                            session_id,
                        )

                finally:
                    break

    except WebSocketDisconnect:
        manager.disconnect(session_id)
