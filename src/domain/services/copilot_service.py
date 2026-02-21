"""
AI Copilot Service

Provides conversational AI assistance with:
- Natural language understanding
- Context-aware responses
- Action execution
- Knowledge retrieval (RAG)
- Multi-turn conversations
"""

import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.ai_copilot import (
    CopilotAction,
    CopilotFeedback,
    CopilotKnowledge,
    CopilotMessage,
    CopilotSession,
)

# ============================================================================
# Action Definitions
# ============================================================================

COPILOT_ACTIONS = {
    "create_incident": {
        "name": "create_incident",
        "display_name": "Create Incident",
        "description": "Create a new incident report",
        "category": "incident",
        "parameters": {
            "title": {"type": "string", "required": True},
            "description": {"type": "string", "required": True},
            "severity": {
                "type": "string",
                "enum": ["low", "medium", "high", "critical"],
            },
            "location": {"type": "string"},
            "incident_type": {"type": "string"},
        },
        "examples": [
            "Create an incident for a slip hazard in warehouse B",
            "Log a near miss in the loading bay",
            "Report a safety concern in the cafeteria",
        ],
    },
    "search_incidents": {
        "name": "search_incidents",
        "display_name": "Search Incidents",
        "description": "Search for incidents matching criteria",
        "category": "incident",
        "parameters": {
            "query": {"type": "string"},
            "status": {"type": "string"},
            "severity": {"type": "string"},
            "date_from": {"type": "string"},
        },
        "examples": [
            "Find all open high severity incidents",
            "Show me incidents from last week",
            "Search for incidents related to PPE",
        ],
    },
    "get_compliance_status": {
        "name": "get_compliance_status",
        "display_name": "Get Compliance Status",
        "description": "Get compliance status for a standard",
        "category": "compliance",
        "parameters": {
            "standard": {
                "type": "string",
                "enum": ["iso9001", "iso14001", "iso45001", "iso27001"],
            },
        },
        "examples": [
            "What's our ISO 9001 status?",
            "How compliant are we with ISO 45001?",
            "Show me our certification status",
        ],
    },
    "schedule_audit": {
        "name": "schedule_audit",
        "display_name": "Schedule Audit",
        "description": "Schedule a new audit",
        "category": "audit",
        "parameters": {
            "audit_type": {"type": "string"},
            "scheduled_date": {"type": "string"},
            "auditor": {"type": "string"},
            "department": {"type": "string"},
        },
        "examples": [
            "Schedule an ISO audit for next month",
            "Set up a workplace safety audit",
        ],
    },
    "create_action": {
        "name": "create_action",
        "display_name": "Create Action",
        "description": "Create a corrective action",
        "category": "action",
        "parameters": {
            "title": {"type": "string", "required": True},
            "description": {"type": "string"},
            "assignee": {"type": "string"},
            "due_date": {"type": "string"},
            "priority": {"type": "string"},
        },
        "examples": [
            "Create an action to fix the broken handrail",
            "Assign a task to review the safety policy",
        ],
    },
    "get_risk_summary": {
        "name": "get_risk_summary",
        "display_name": "Get Risk Summary",
        "description": "Get summary of current risks",
        "category": "risk",
        "parameters": {
            "category": {"type": "string"},
            "min_score": {"type": "integer"},
        },
        "examples": [
            "Show me high risks",
            "What are our top 10 risks?",
            "Summarize operational risks",
        ],
    },
    "navigate": {
        "name": "navigate",
        "display_name": "Navigate",
        "description": "Navigate to a page in the application",
        "category": "navigation",
        "parameters": {
            "destination": {"type": "string", "required": True},
        },
        "examples": [
            "Go to the dashboard",
            "Open the incidents page",
            "Take me to settings",
        ],
    },
    "explain": {
        "name": "explain",
        "display_name": "Explain",
        "description": "Explain a concept or term",
        "category": "knowledge",
        "parameters": {
            "topic": {"type": "string", "required": True},
        },
        "examples": [
            "What is a CAPA?",
            "Explain ISO 45001",
            "What does RIDDOR mean?",
        ],
    },
}


# ============================================================================
# System Prompts
# ============================================================================

SYSTEM_PROMPT = """You are an AI assistant for a Quality, Health, Safety, and Environment (QHSE) management platform. You help users with:

1. **Incident Management**: Creating, searching, and managing incident reports
2. **Audit Management**: Scheduling audits, reviewing findings, managing CAPAs
3. **Risk Management**: Identifying, assessing, and mitigating risks
4. **Compliance**: Tracking ISO certifications, managing documentation
5. **Actions**: Creating and tracking corrective and preventive actions

You have access to the following actions you can perform:
{actions}

When a user asks you to do something, determine if it requires an action. If so, respond with:
```action
{{
  "action": "action_name",
  "parameters": {{...}}
}}
```

Guidelines:
- Be concise but helpful
- Use industry terminology appropriately
- If unsure, ask clarifying questions
- Prioritize safety-related requests
- Reference relevant regulations when appropriate (ISO, HSE, RIDDOR)
- Be proactive in suggesting related actions

Current context: {context}
"""


class CopilotService:
    """
    AI Copilot conversation service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._ai_client = None

    # =========================================================================
    # Session Management
    # =========================================================================

    async def create_session(
        self,
        tenant_id: int,
        user_id: int,
        context_type: Optional[str] = None,
        context_id: Optional[str] = None,
        context_data: Optional[dict] = None,
        current_page: Optional[str] = None,
    ) -> CopilotSession:
        """Create a new copilot conversation session."""
        session = CopilotSession(
            tenant_id=tenant_id,
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
            context_data=context_data or {},
            current_page=current_page,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        return session

    async def get_session(self, session_id: int) -> Optional[CopilotSession]:
        """Get a session by ID."""
        result = await self.db.execute(select(CopilotSession).where(CopilotSession.id == session_id))
        return result.scalar_one_or_none()

    async def get_active_session(self, user_id: int) -> Optional[CopilotSession]:
        """Get the user's active session."""
        result = await self.db.execute(
            select(CopilotSession)
            .where(CopilotSession.user_id == user_id, CopilotSession.is_active == True)
            .order_by(CopilotSession.updated_at.desc())
        )
        return result.scalars().first()

    async def get_session_messages(self, session_id: int, limit: int = 50) -> list[CopilotMessage]:
        """Get messages for a session."""
        result = await self.db.execute(
            select(CopilotMessage)
            .where(CopilotMessage.session_id == session_id)
            .order_by(CopilotMessage.created_at)
            .limit(limit)
        )
        return result.scalars().all()

    async def close_session(self, session_id: int) -> CopilotSession:
        """Close a session."""
        session = await self.get_session(session_id)
        if session:
            session.is_active = False
            await self.db.commit()
            await self.db.refresh(session)
        return session

    # =========================================================================
    # Conversation
    # =========================================================================

    async def send_message(
        self,
        session_id: int,
        content: str,
        user_id: int,
    ) -> CopilotMessage:
        """
        Send a message and get AI response.
        """
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Save user message
        user_message = CopilotMessage(
            session_id=session_id,
            role="user",
            content=content,
        )
        self.db.add(user_message)
        await self.db.commit()

        # Get conversation history
        history = await self.get_session_messages(session_id, limit=20)

        # Build context
        context = self._build_context(session)

        # Generate AI response
        start_time = time.time()
        response_content, action_data = await self._generate_response(content, history, context)
        latency_ms = int((time.time() - start_time) * 1000)

        # Save assistant message
        assistant_message = CopilotMessage(
            session_id=session_id,
            role="assistant",
            content=response_content,
            content_type="action" if action_data else "text",
            action_type=action_data.get("action") if action_data else None,
            action_data=action_data.get("parameters") if action_data else None,
            action_status="pending" if action_data else None,
            model_used="gpt-4-turbo",
            latency_ms=latency_ms,
        )
        self.db.add(assistant_message)

        # Update session
        session.last_message_at = datetime.now(timezone.utc)
        if not session.title and len(content) > 0:
            session.title = content[:50] + ("..." if len(content) > 50 else "")

        await self.db.commit()
        await self.db.refresh(assistant_message)

        # Execute action if present
        if action_data:
            await self._execute_action(assistant_message, action_data)

        return assistant_message

    async def _generate_response(
        self,
        user_message: str,
        history: list[CopilotMessage],
        context: dict,
    ) -> tuple[str, Optional[dict]]:
        """Generate AI response using the configured AI provider."""

        # Build messages for AI
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT.format(
                    actions=json.dumps(list(COPILOT_ACTIONS.keys()), indent=2),
                    context=json.dumps(context, indent=2),
                ),
            }
        ]

        # Add history
        for msg in history[-10:]:  # Last 10 messages
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        # In production, this would call the actual AI API
        # For now, we'll use pattern matching for demo
        response_content, action_data = self._simulate_ai_response(user_message, context)

        return response_content, action_data

    def _simulate_ai_response(
        self,
        user_message: str,
        context: dict,
    ) -> tuple[str, Optional[dict]]:
        """Simulate AI response for demo purposes."""
        message_lower = user_message.lower()

        # Create incident
        if any(
            word in message_lower
            for word in [
                "create incident",
                "log incident",
                "report incident",
                "new incident",
            ]
        ):
            # Extract title from message
            title = user_message
            if ":" in user_message:
                title = user_message.split(":", 1)[1].strip()
            elif "for" in message_lower:
                title = user_message.split("for", 1)[1].strip()

            return (
                f"I'll create an incident report for you. Here are the details I've extracted:\n\n"
                f"**Title:** {title}\n"
                f"**Severity:** Medium (you can adjust this)\n\n"
                f"Shall I proceed with creating this incident?",
                {
                    "action": "create_incident",
                    "parameters": {
                        "title": title,
                        "severity": "medium",
                    },
                },
            )

        # Compliance status
        if "compliance" in message_lower or "iso" in message_lower:
            standard = "iso9001"
            if "14001" in message_lower:
                standard = "iso14001"
            elif "45001" in message_lower:
                standard = "iso45001"
            elif "27001" in message_lower:
                standard = "iso27001"

            return (
                f"Here's your current {standard.upper()} compliance status:\n\n"
                f"📊 **Overall Compliance:** 92%\n"
                f"✅ **Clauses Compliant:** 45/49\n"
                f"⚠️ **Minor Gaps:** 3\n"
                f"❌ **Major Gaps:** 1\n\n"
                f"The major gap is in Clause 8.5.1 (Control of production). "
                f"Would you like me to show you the detailed gap analysis or create actions to address these gaps?",
                {
                    "action": "get_compliance_status",
                    "parameters": {"standard": standard},
                },
            )

        # Risk summary
        if "risk" in message_lower:
            return (
                f"Here's your current risk summary:\n\n"
                f"🔴 **Critical Risks:** 2\n"
                f"🟠 **High Risks:** 8\n"
                f"🟡 **Medium Risks:** 15\n"
                f"🟢 **Low Risks:** 23\n\n"
                f"**Top Risk:** Supply chain disruption (Score: 20)\n"
                f"**Most Recent:** Cybersecurity threat (Added today)\n\n"
                f"Would you like to see the risk heat map or create a treatment plan?",
                None,
            )

        # Explain something
        if message_lower.startswith("what is") or message_lower.startswith("explain"):
            topic = user_message.split(" ", 2)[-1].strip("?")

            explanations = {
                "capa": "**CAPA (Corrective and Preventive Action)** is a systematic approach to:\n\n"
                "1. **Corrective Action:** Fix the immediate problem and its root cause\n"
                "2. **Preventive Action:** Prevent similar problems from occurring\n\n"
                "CAPAs are required by ISO 9001 (Clause 10.2) and are essential for continuous improvement.",
                "riddor": "**RIDDOR (Reporting of Injuries, Diseases and Dangerous Occurrences Regulations)** "
                "is UK legislation requiring employers to report:\n\n"
                "• Deaths and specified injuries\n"
                "• Over-7-day incapacitation\n"
                "• Occupational diseases\n"
                "• Dangerous occurrences\n\n"
                "Reports must be made to the HSE within 10-15 days depending on severity.",
                "iso 45001": "**ISO 45001** is the international standard for Occupational Health & Safety Management Systems.\n\n"
                "Key elements:\n"
                "• Leadership commitment\n"
                "• Worker participation\n"
                "• Hazard identification\n"
                "• Legal compliance\n"
                "• Continual improvement\n\n"
                "It replaced OHSAS 18001 in 2018.",
            }

            explanation = explanations.get(
                topic.lower(),
                f"**{topic}** is a term used in quality and safety management. "
                f"Would you like me to search our knowledge base for more specific information?",
            )

            return (explanation, None)

        # Navigation
        if any(word in message_lower for word in ["go to", "open", "show me", "navigate"]):
            destinations = {
                "dashboard": "/",
                "incidents": "/incidents",
                "audits": "/audits",
                "risks": "/risks",
                "settings": "/settings",
                "reports": "/reports",
            }

            for dest, path in destinations.items():
                if dest in message_lower:
                    return (
                        f"Taking you to the {dest} page.",
                        {
                            "action": "navigate",
                            "parameters": {"destination": path},
                        },
                    )

        # Default response
        return (
            f'I understand you\'re asking about: "{user_message}"\n\n'
            f"I can help you with:\n"
            f"• 📝 Creating and managing incidents\n"
            f"• 📋 Scheduling and tracking audits\n"
            f"• ⚠️ Risk assessment and management\n"
            f"• ✅ Compliance tracking\n"
            f"• 📊 Generating reports\n\n"
            f"What would you like to do?",
            None,
        )

    async def _execute_action(
        self,
        message: CopilotMessage,
        action_data: dict,
    ) -> None:
        """Execute a copilot action."""
        action_name = action_data.get("action")
        parameters = action_data.get("parameters", {})

        try:
            result = None

            if action_name == "navigate":
                result = {
                    "navigated": True,
                    "destination": parameters.get("destination"),
                }

            elif action_name == "create_incident":
                result = {
                    "created": True,
                    "incident_id": "INC-2026-0100",
                    "title": parameters.get("title"),
                }

            elif action_name == "get_compliance_status":
                result = {
                    "standard": parameters.get("standard"),
                    "compliance_percentage": 92,
                    "gaps": 4,
                }

            # Update message with result
            message.action_result = result
            message.action_status = "completed"

        except Exception as e:
            message.action_status = "failed"
            message.action_result = {"error": str(e)}

        await self.db.commit()

    def _build_context(self, session: CopilotSession) -> dict:
        """Build context information for the AI."""
        return {
            "current_page": session.current_page,
            "context_type": session.context_type,
            "context_id": session.context_id,
            "context_data": session.context_data,
        }

    # =========================================================================
    # Feedback
    # =========================================================================

    async def submit_feedback(
        self,
        message_id: int,
        user_id: int,
        tenant_id: int,
        rating: int,
        feedback_type: str,
        feedback_text: Optional[str] = None,
    ) -> CopilotFeedback:
        """Submit feedback on a copilot response."""
        result = await self.db.execute(select(CopilotMessage).where(CopilotMessage.id == message_id))
        message = result.scalar_one_or_none()

        if not message:
            raise ValueError(f"Message {message_id} not found")

        # Get the user query (previous message)
        result = await self.db.execute(
            select(CopilotMessage)
            .where(
                CopilotMessage.session_id == message.session_id,
                CopilotMessage.role == "user",
                CopilotMessage.created_at < message.created_at,
            )
            .order_by(CopilotMessage.created_at.desc())
        )
        user_query_msg = result.scalars().first()

        feedback = CopilotFeedback(
            tenant_id=tenant_id,
            user_id=user_id,
            message_id=message_id,
            rating=rating,
            feedback_type=feedback_type,
            feedback_text=feedback_text,
            user_query=user_query_msg.content if user_query_msg else "",
            assistant_response=message.content,
        )

        self.db.add(feedback)

        # Also update the message
        message.feedback_rating = rating
        message.feedback_text = feedback_text

        await self.db.commit()
        await self.db.refresh(feedback)

        return feedback

    # =========================================================================
    # Knowledge Base
    # =========================================================================

    async def search_knowledge(
        self,
        query: str,
        tenant_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> list[CopilotKnowledge]:
        """Search the knowledge base."""
        stmt = select(CopilotKnowledge).where(
            CopilotKnowledge.is_active == True,
        )

        if tenant_id:
            stmt = stmt.where((CopilotKnowledge.tenant_id == tenant_id) | (CopilotKnowledge.tenant_id == None))

        if category:
            stmt = stmt.where(CopilotKnowledge.category == category)

        stmt = stmt.where(CopilotKnowledge.content.ilike(f"%{query}%") | CopilotKnowledge.title.ilike(f"%{query}%"))

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_knowledge(
        self,
        title: str,
        content: str,
        category: str,
        tenant_id: Optional[int] = None,
        tags: Optional[list] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> CopilotKnowledge:
        """Add to the knowledge base."""
        knowledge = CopilotKnowledge(
            tenant_id=tenant_id,
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source_type=source_type,
            source_id=source_id,
        )

        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)

        return knowledge
