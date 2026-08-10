"""
PlantEx Assist service (technical module: AI Copilot)

Provides conversational AI assistance with:
- Natural language understanding
- Context-aware responses
- Action execution
- Knowledge retrieval (RAG)
- Multi-turn conversations
"""

import re
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.models.ai_copilot import (
    CopilotAction,
    CopilotFeedback,
    CopilotKnowledge,
    CopilotMessage,
    CopilotSession,
)
from src.domain.services.copilot_kill_switch import copilot_kill_switch_last_known


class CopilotDisabledError(RuntimeError):
    """Raised when a simulated copilot reply is requested while the feature flag is off."""


def copilot_is_enabled() -> bool:
    """Whether configuration permits copilot output to be served (PX-248).

    Fails closed like the frontend gate: no environment is eligible without an explicit
    opt-in, and the shipped default is off. Production is eligible on the same terms as
    every other environment — the operator setting AI_COPILOT_ENABLED is accepting that
    the replies are keyword simulations, which the UI states before the first exchange.

    This is the configuration gate only. It is also the *first* gate: the runtime kill
    switch in :mod:`src.domain.services.copilot_kill_switch` is consulted after this
    returns ``True``, never instead of it, which is what keeps the database able to close
    the surface and unable to open it.
    """
    return settings.ai_copilot_enabled


def copilot_inference_is_enabled() -> bool:
    """Whether grounded inference (PR3b) may run.

    Requires the surface gate (``AI_COPILOT_ENABLED``) *and* the inference gate
    (``AI_COPILOT_INFERENCE_ENABLED``, default off). When PR3a (#1481) has landed,
    also respects the subtract-only kill switch's last known verdict without doing
    I/O here — same posture as ``send_message`` on that branch.
    """
    if not copilot_is_enabled():
        return False
    if not settings.ai_copilot_inference_enabled:
        return False
    try:
        from src.domain.services.copilot_kill_switch import copilot_kill_switch_last_known
    except ImportError:
        return True
    return not copilot_kill_switch_last_known()


# ============================================================================
# Refusal copy
# ============================================================================
#
# Three different things can stop an answer, and one sentence cannot describe all
# three without being false about two of them:
#
#   * inference off      — no registers are read at all; the replies really are
#                          hardcoded keyword matches, so "not connected" is true.
#   * inference on, no   — the registers *are* wired up; the limit is the closed
#     matching intent      question set, not the connection.
#   * inference on, the  — the question was in the set and the figures were
#     citation check       computed, but the wording quoted something that is not
#     failed               in them, so the answer is dropped unserved.
#
# Wording the middle and last cases as a disconnected demo is the defect these
# constants exist to remove: it understates a surface that answers register
# questions in the very next breath, which teaches users to disbelieve the
# disclaimers that matter.

DEMO_LIVE_DATA_REFUSAL = (
    "I cannot answer from live organisation data. This PlantEx Assist demo is not "
    "connected to your registers, so I will not invent counts, percentages, named "
    "risks, or reference numbers. Open the relevant module for real figures."
)

OUT_OF_SET_REFUSAL = (
    "That is outside the fixed set of questions PlantEx Assist answers from your "
    "registers, so I will not invent counts, percentages, named risks, or reference "
    "numbers. Try a supported question — for example how many incidents we have, or "
    "which actions are overdue — or open the relevant module for real figures."
)

CITATION_REFUSAL = (
    "I could not verify every figure in that answer against your own registers, so I "
    "have dropped it rather than serve it. PlantEx Assist only quotes counts, "
    "percentages and reference numbers that appear in the figures this platform "
    "computed. Open the relevant module for the live register."
)

DEMO_WRITE_REFUSAL = (
    "I cannot create or update records from this PlantEx Assist demo. Nothing was written. "
    "Use the Incidents register (New) to log a real safety event."
)

GROUNDED_WRITE_REFUSAL = (
    "PlantEx Assist never creates, edits or deletes records. Nothing was written. "
    "Use the Incidents register (New) to log a real safety event."
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
    PlantEx Assist conversation service.
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

    async def get_session(
        self,
        session_id: int,
        *,
        user_id: int,
        tenant_id: int,
    ) -> Optional[CopilotSession]:
        """Get a session by ID scoped to the owning user and tenant."""
        result = await self.db.execute(
            select(CopilotSession).where(
                CopilotSession.id == session_id,
                CopilotSession.user_id == user_id,
                CopilotSession.tenant_id == tenant_id,
            )
        )
        return result.scalars().first()

    async def get_active_session(self, user_id: int, tenant_id: int) -> Optional[CopilotSession]:
        """Get the user's active session within a tenant."""
        result = await self.db.execute(
            select(CopilotSession)
            .where(
                CopilotSession.user_id == user_id,
                CopilotSession.tenant_id == tenant_id,
                CopilotSession.is_active == True,
            )
            .order_by(CopilotSession.updated_at.desc())
        )
        return result.scalars().first()

    async def get_session_messages(
        self,
        session_id: int,
        *,
        user_id: int,
        tenant_id: int,
        limit: int = 50,
    ) -> list[CopilotMessage]:
        """Get messages for a session owned by the caller."""
        session = await self.get_session(session_id, user_id=user_id, tenant_id=tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        result = await self.db.execute(
            select(CopilotMessage)
            .where(CopilotMessage.session_id == session_id)
            .order_by(CopilotMessage.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def close_session(
        self,
        session_id: int,
        *,
        user_id: int,
        tenant_id: int,
    ) -> CopilotSession:
        """Close a session owned by the caller."""
        session = await self.get_session(session_id, user_id=user_id, tenant_id=tenant_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

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
        *,
        user_id: int,
        tenant_id: int,
    ) -> CopilotMessage:
        """
        Send a message and get AI response.
        """
        # PX-248: the reply is fabricated, so refuse before anything is persisted.
        # The API layer already returns 404, but this closes non-HTTP callers too.
        if not copilot_is_enabled():
            raise CopilotDisabledError("PlantEx Assist is disabled; simulated responses must not be served.")

        # Second line behind the API guards, which are the ones that refresh the switch.
        # Deliberately does not read the database: this method runs on a caller's session
        # and a failed read would leave that session unusable for the caller's own work.
        # A process that has never refreshed therefore sees no kill here — see
        # copilot_kill_switch_last_known.
        if copilot_kill_switch_last_known():
            raise CopilotDisabledError("PlantEx Assist has been closed by the runtime kill switch.")

        session = await self.get_session(session_id, user_id=user_id, tenant_id=tenant_id)
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
        history = await self.get_session_messages(session_id, user_id=user_id, tenant_id=tenant_id, limit=20)

        # Build context
        context = self._build_context(session)

        # Generate AI response
        start_time = time.time()
        response_content, action_data, model_used = await self._generate_response(
            content,
            history,
            context,
            tenant_id=tenant_id,
            user_id=user_id,
        )
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
            model_used=model_used,
            latency_ms=latency_ms,
        )
        self.db.add(assistant_message)

        # Update session — TIMESTAMP WITHOUT TIME ZONE columns need naive UTC
        # (asyncpg DataError on aware datetimes; prod: "what is CAPA" → 500).
        session.last_message_at = datetime.now(timezone.utc).replace(tzinfo=None)
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
        *,
        tenant_id: int,
        user_id: Optional[int] = None,
    ) -> tuple[str, Optional[dict], str]:
        """Generate AI response — grounded when the inference flag is on and the
        question matches a closed intent; otherwise the honesty simulator.

        ``user_id`` is forwarded because some grounded intents are permission-gated
        and the tenant alone does not say whether this caller may see the figure.
        """
        grounded = copilot_inference_is_enabled()

        if grounded:
            from src.domain.services.copilot_grounding import CopilotGroundingService

            outcome = await CopilotGroundingService(self.db).try_answer(
                user_message,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            if outcome.kind == "answered" and outcome.content is not None:
                return outcome.content, None, outcome.model_used or "grounded-facts"
            if outcome.kind == "refused":
                return CITATION_REFUSAL, None, "grounded-citation-refused"

        # ``ungrounded`` lands here: the intent is outside the closed set, or it is a
        # permission-gated one the caller may not read. Both fall through to the same
        # keyword replies, which is what keeps those two cases indistinguishable from
        # outside (see CopilotGroundingService.try_answer). ``grounded`` only changes
        # the wording, and it reads a deployment-wide flag rather than anything about
        # this caller, so that indistinguishability survives.
        response_content, action_data = self._simulate_ai_response(user_message, context, grounded=grounded)
        return response_content, action_data, "simulated-keyword-match"

    def _simulate_ai_response(
        self,
        user_message: str,
        context: dict,
        *,
        grounded: bool = False,
    ) -> tuple[str, Optional[dict]]:
        """Keyword replies — refuse live-data fabrication and false writes (PX-248/250).

        ``grounded`` says whether inference is open in this deployment, and it exists
        because the refusals below cannot be worded the same way in both cases. With
        inference off the surface really is a disconnected keyword demo and should say
        so; with it on the registers are wired up and the limit is the closed question
        set, so "this demo is not connected to your registers" would be a false
        disclaimer about a surface that answers register questions two sentences later.
        """
        message_lower = user_message.lower()
        live_data_refusal = OUT_OF_SET_REFUSAL if grounded else DEMO_LIVE_DATA_REFUSAL
        write_refusal = GROUNDED_WRITE_REFUSAL if grounded else DEMO_WRITE_REFUSAL

        # Create incident — honest refusal, never "Shall I proceed?" + false success (PX-250).
        if "incident" in message_lower and any(word in message_lower for word in ("create", "log", "report", "new")):
            return (
                write_refusal,
                {
                    "action": "create_incident",
                    "parameters": {"title": user_message},
                    "honesty": "not_performed",
                },
            )

        # Compliance / ISO live status — refuse fabricated percentages (PX-248).
        if ("compliance" in message_lower or "iso" in message_lower) and not (
            message_lower.startswith("what is") or message_lower.startswith("explain")
        ):
            standard = "iso9001"
            if "14001" in message_lower:
                standard = "iso14001"
            elif "45001" in message_lower:
                standard = "iso45001"
            elif "27001" in message_lower:
                standard = "iso27001"
            return (
                f"{live_data_refusal}\n\nFor ISO clause scores, open Compliance in the main navigation.",
                {
                    "action": "get_compliance_status",
                    "parameters": {"standard": standard},
                    "honesty": "not_performed",
                },
            )

        # Risk summaries — refuse invented named risks / counts (PX-248).
        if re.search(r"\brisks?\b", message_lower) and not (
            message_lower.startswith("what is") or message_lower.startswith("explain")
        ):
            return (
                f"{live_data_refusal}\n\nOpen the Risk Register for the live register.",
                {
                    "action": "get_risk_summary",
                    "parameters": {},
                    "honesty": "not_performed",
                },
            )

        # Explain something — general guidance only (not tenant data).
        if message_lower.startswith("what is") or message_lower.startswith("explain"):
            topic = user_message.split(" ", 2)[-1].strip("?")

            explanations = {
                "capa": "**CAPA (Corrective and Preventive Action)** is a systematic approach to:\n\n"
                "1. **Corrective Action:** Fix the immediate problem and its root cause\n"
                "2. **Preventive Action:** Prevent similar problems from occurring\n\n"
                "CAPAs are required by ISO 9001 (Clause 10.2). "
                "_General guidance only — not your organisation's CAPA register._",
                "riddor": "**RIDDOR (Reporting of Injuries, Diseases and Dangerous Occurrences Regulations)** "
                "is UK legislation requiring employers to report:\n\n"
                "• Deaths and specified injuries\n"
                "• Over-7-day incapacitation\n"
                "• Occupational diseases\n"
                "• Dangerous occurrences\n\n"
                "Reports must be made to the HSE within 10-15 days depending on severity. "
                "_General guidance only._",
                "iso 45001": "**ISO 45001** is the international standard for Occupational Health & Safety Management Systems.\n\n"
                "Key elements:\n"
                "• Leadership commitment\n"
                "• Worker participation\n"
                "• Hazard identification\n"
                "• Legal compliance\n"
                "• Continual improvement\n\n"
                "_General guidance only — not your compliance score._",
            }

            no_lookup = (
                "PlantEx Assist answers a fixed set of register questions and cannot look up "
                "this term in your organisation's records."
                if grounded
                else "This PlantEx Assist demo cannot look up your organisation's records."
            )
            explanation = explanations.get(
                topic.lower(),
                f"**{topic}** is a term used in quality and safety management. {no_lookup}",
            )

            return (explanation, None)

        # Navigation hint only — client may navigate; no fabricated write.
        if any(word in message_lower for word in ["go to", "open", "show me", "navigate"]):
            destinations = {
                "dashboard": "/",
                "incidents": "/incidents",
                "audits": "/audits",
                "risks": "/risks",
                "settings": "/settings",
                "reports": "/reports",
            }

            no_navigation = (
                "PlantEx Assist does not perform navigation for you."
                if grounded
                else "This PlantEx Assist demo does not perform navigation for you."
            )
            for dest, path in destinations.items():
                if dest in message_lower:
                    return (
                        f"Open {path} in the application navigation for the {dest} page. {no_navigation}",
                        {
                            "action": "navigate",
                            "parameters": {"destination": path},
                            "honesty": "not_performed",
                        },
                    )

        scope = (
            "PlantEx Assist answers a fixed set of questions from your registers and can "
            "explain QHSE concepts. Anything outside that set I refuse rather than guess, "
            "and I never write to a register."
            if grounded
            else "In this PlantEx Assist demo I can explain QHSE concepts and will refuse "
            "live-data questions and writes. I will not invent register data."
        )
        return (
            f'I understand you\'re asking about: "{user_message}"\n\n{scope}\n\nWhat would you like to do?',
            None,
        )

    async def _execute_action(
        self,
        message: CopilotMessage,
        action_data: dict,
    ) -> None:
        """Record honesty outcome for a proposed action — never fake a successful write."""
        action_name = action_data.get("action")
        parameters = action_data.get("parameters", {})
        honesty = action_data.get("honesty")

        try:
            # PX-250 / PX-248: simulated paths must not claim completion or fabricate IDs.
            if honesty == "not_performed" or action_name in {
                "create_incident",
                "get_compliance_status",
                "get_risk_summary",
                "navigate",
            }:
                # The stored reason is the machine-readable half of the same disclosure
                # the panel shows, so it has to track the deployment for the same reason
                # the wording does: "demo cannot read live data" is untrue of a
                # deployment whose grounded intents are reading registers.
                message.action_result = {
                    "performed": False,
                    "action": action_name,
                    "parameters": parameters,
                    "reason": (
                        "assist_never_writes_or_reads_outside_grounded_set"
                        if copilot_inference_is_enabled()
                        else "demo_cannot_read_or_write_live_data"
                    ),
                }
                message.action_status = "not_performed"
            else:
                message.action_result = {
                    "performed": False,
                    "action": action_name,
                    "reason": "unsupported_action",
                }
                message.action_status = "not_performed"

        except Exception as e:
            message.action_status = "failed"
            message.action_result = {"error": str(e), "performed": False}

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
        result = await self.db.execute(
            select(CopilotMessage)
            .join(CopilotSession, CopilotMessage.session_id == CopilotSession.id)
            .where(
                CopilotMessage.id == message_id,
                CopilotSession.user_id == user_id,
                CopilotSession.tenant_id == tenant_id,
            )
        )
        message = result.scalars().first()

        if not message:
            raise ValueError(f"Message {message_id} not found")

        # Get the user query (previous message)
        uq_result = await self.db.execute(
            select(CopilotMessage)
            .where(
                CopilotMessage.session_id == message.session_id,
                CopilotMessage.role == "user",
                CopilotMessage.created_at < message.created_at,
            )
            .order_by(CopilotMessage.created_at.desc())
        )
        user_query_msg = uq_result.scalars().first()

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
        stmt = select(CopilotKnowledge).where(CopilotKnowledge.is_active == True)

        if tenant_id:
            stmt = stmt.where((CopilotKnowledge.tenant_id == tenant_id) | (CopilotKnowledge.tenant_id == None))

        if category:
            stmt = stmt.where(CopilotKnowledge.category == category)

        stmt = stmt.where(
            CopilotKnowledge.content.ilike(f"%{query}%") | CopilotKnowledge.title.ilike(f"%{query}%")
        ).limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

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
