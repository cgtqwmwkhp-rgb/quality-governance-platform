"""
Workflow Engine - Intelligent Workflow Automation

Features:
- Workflow template execution
- Approval chain management
- Auto-escalation
- Conditional routing
- SLA tracking
- Bulk operations
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Smart workflow engine for automated process management.

    Handles:
    - Starting workflows from templates
    - Processing approval chains
    - Auto-escalation based on SLA
    - Conditional routing
    - Delegation management
    """

    def __init__(self) -> None:
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._load_default_templates()

    def _load_default_templates(self) -> None:
        """Load built-in workflow templates."""
        self.templates = {
            "RIDDOR": {
                "code": "RIDDOR",
                "name": "RIDDOR Reporting Workflow",
                "description": "Mandatory HSE notification for reportable incidents",
                "category": "regulatory",
                "trigger_entity_type": "incident",
                "trigger_conditions": {"severity": ["critical", "major"], "is_riddor": True},
                "sla_hours": 24,
                "warning_hours": 20,
                "steps": [
                    {
                        "name": "Initial Review",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["safety_manager"],
                        "sla_hours": 4,
                    },
                    {
                        "name": "HSE Notification",
                        "type": "task",
                        "assignee_role": "safety_manager",
                        "sla_hours": 8,
                    },
                    {
                        "name": "Management Sign-off",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["operations_director"],
                        "sla_hours": 4,
                    },
                    {
                        "name": "Final Submission",
                        "type": "task",
                        "assignee_role": "compliance_officer",
                        "sla_hours": 4,
                    },
                ],
                "escalation_rules": [
                    {
                        "trigger": "sla_breach",
                        "escalate_to": "operations_director",
                        "priority": "critical",
                    }
                ],
            },
            "CAPA": {
                "code": "CAPA",
                "name": "Corrective/Preventive Action Workflow",
                "description": "Track and verify corrective and preventive actions",
                "category": "quality",
                "trigger_entity_type": "action",
                "trigger_conditions": {"type": ["corrective", "preventive"]},
                "sla_hours": 168,  # 7 days
                "warning_hours": 120,
                "steps": [
                    {
                        "name": "Root Cause Analysis",
                        "type": "task",
                        "assignee": "action_owner",
                        "sla_hours": 48,
                    },
                    {
                        "name": "Action Plan Review",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["quality_manager"],
                        "sla_hours": 24,
                    },
                    {
                        "name": "Implementation",
                        "type": "task",
                        "assignee": "action_owner",
                        "sla_hours": 72,
                    },
                    {
                        "name": "Effectiveness Verification",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["quality_manager"],
                        "sla_hours": 24,
                    },
                ],
            },
            "NCR": {
                "code": "NCR",
                "name": "Non-Conformance Report Workflow",
                "description": "Handle non-conformances through to resolution",
                "category": "quality",
                "trigger_entity_type": "audit_finding",
                "trigger_conditions": {"type": "non_conformance"},
                "sla_hours": 72,
                "warning_hours": 48,
                "steps": [
                    {
                        "name": "NCR Registration",
                        "type": "task",
                        "assignee_role": "quality_team",
                        "sla_hours": 8,
                    },
                    {
                        "name": "Root Cause Investigation",
                        "type": "task",
                        "assignee": "finding_owner",
                        "sla_hours": 24,
                    },
                    {
                        "name": "Corrective Action Plan",
                        "type": "approval",
                        "approval_type": "parallel",
                        "approvers": ["quality_manager", "department_head"],
                        "sla_hours": 16,
                    },
                    {
                        "name": "Implementation & Closure",
                        "type": "task",
                        "assignee": "finding_owner",
                        "sla_hours": 24,
                    },
                ],
            },
            "INCIDENT_INVESTIGATION": {
                "code": "INCIDENT_INVESTIGATION",
                "name": "Incident Investigation Workflow",
                "description": "Structured incident investigation process",
                "category": "safety",
                "trigger_entity_type": "incident",
                "trigger_conditions": {"requires_investigation": True},
                "sla_hours": 120,
                "warning_hours": 96,
                "steps": [
                    {
                        "name": "Initial Assessment",
                        "type": "task",
                        "assignee_role": "safety_manager",
                        "sla_hours": 4,
                    },
                    {
                        "name": "Evidence Collection",
                        "type": "task",
                        "assignee_role": "investigator",
                        "sla_hours": 24,
                    },
                    {
                        "name": "Root Cause Analysis",
                        "type": "task",
                        "assignee_role": "investigator",
                        "sla_hours": 48,
                    },
                    {
                        "name": "Findings Review",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["safety_manager", "operations_manager"],
                        "sla_hours": 24,
                    },
                    {
                        "name": "Action Assignment",
                        "type": "task",
                        "assignee_role": "safety_manager",
                        "sla_hours": 8,
                    },
                    {
                        "name": "Management Sign-off",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["operations_director"],
                        "sla_hours": 16,
                    },
                ],
            },
            "DOCUMENT_APPROVAL": {
                "code": "DOCUMENT_APPROVAL",
                "name": "Document Approval Workflow",
                "description": "Review and approve new/updated documents",
                "category": "documents",
                "trigger_entity_type": "document",
                "trigger_conditions": {"status": "pending_approval"},
                "sla_hours": 48,
                "warning_hours": 36,
                "steps": [
                    {
                        "name": "Technical Review",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["document_owner"],
                        "sla_hours": 24,
                    },
                    {
                        "name": "Quality Review",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["quality_manager"],
                        "sla_hours": 16,
                    },
                    {
                        "name": "Final Approval",
                        "type": "approval",
                        "approval_type": "sequential",
                        "approvers": ["document_controller"],
                        "sla_hours": 8,
                    },
                ],
            },
        }

    # ==================== Workflow Management ====================

    def start_workflow(
        self,
        template_code: str,
        entity_type: str,
        entity_id: str,
        initiated_by: int,
        context: Optional[Dict[str, Any]] = None,
        priority: str = "normal",
    ) -> Dict[str, Any]:
        """
        Start a new workflow instance from a template.

        Args:
            template_code: Template to use
            entity_type: Type of entity this workflow is for
            entity_id: ID of the entity
            initiated_by: User starting the workflow
            context: Additional context data
            priority: Workflow priority

        Returns:
            Workflow instance details
        """
        template = self.templates.get(template_code)
        if not template:
            return {"error": f"Template not found: {template_code}"}

        now = datetime.utcnow()
        sla_due = now + timedelta(hours=template.get("sla_hours", 72))
        warning_at = now + timedelta(hours=template.get("warning_hours", 48))

        instance = {
            "id": f"WF-{now.strftime('%Y%m%d%H%M%S')}",
            "template_code": template_code,
            "template_name": template["name"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": "in_progress",
            "priority": priority,
            "current_step": 0,
            "current_step_name": template["steps"][0]["name"],
            "total_steps": len(template["steps"]),
            "initiated_by": initiated_by,
            "sla_due_at": sla_due.isoformat(),
            "sla_warning_at": warning_at.isoformat(),
            "sla_breached": False,
            "started_at": now.isoformat(),
            "context": context or {},
            "steps": self._initialize_steps(template["steps"], now),
        }

        logger.info(f"Started workflow {instance['id']} from template {template_code}")

        return instance

    def _initialize_steps(self, step_definitions: List[Dict], start_time: datetime) -> List[Dict[str, Any]]:
        """Initialize step records from definitions."""
        steps = []
        cumulative_hours = 0

        for i, step_def in enumerate(step_definitions):
            step_sla = step_def.get("sla_hours", 24)
            cumulative_hours += step_sla
            due_at = start_time + timedelta(hours=cumulative_hours)

            steps.append(
                {
                    "step_number": i,
                    "name": step_def["name"],
                    "type": step_def["type"],
                    "status": "pending" if i > 0 else "in_progress",
                    "approval_type": step_def.get("approval_type"),
                    "approvers": step_def.get("approvers", []),
                    "assignee": step_def.get("assignee"),
                    "assignee_role": step_def.get("assignee_role"),
                    "sla_hours": step_sla,
                    "due_at": due_at.isoformat(),
                    "started_at": start_time.isoformat() if i == 0 else None,
                    "completed_at": None,
                    "outcome": None,
                }
            )

        return steps

    def advance_workflow(
        self,
        workflow_id: str,
        outcome: str,
        outcome_by: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Advance workflow to next step or complete.

        Args:
            workflow_id: Workflow instance ID
            outcome: Step outcome (approved, rejected, completed)
            outcome_by: User completing the step
            notes: Optional notes

        Returns:
            Updated workflow state
        """
        now = datetime.utcnow()

        # Mock response - in production would update database
        return {
            "workflow_id": workflow_id,
            "action": "advanced",
            "outcome": outcome,
            "outcome_by": outcome_by,
            "notes": notes,
            "next_step": "Effectiveness Verification",
            "timestamp": now.isoformat(),
        }

    # ==================== Approval Management ====================

    def get_pending_approvals(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all pending approvals for a user."""
        # Mock data
        return [
            {
                "id": "APR-001",
                "workflow_id": "WF-20260119001",
                "workflow_name": "RIDDOR Reporting",
                "step_name": "Management Sign-off",
                "entity_type": "incident",
                "entity_id": "INC-2026-0042",
                "entity_title": "Slip and fall incident - Site A",
                "requested_at": "2026-01-19T10:00:00Z",
                "due_at": "2026-01-19T14:00:00Z",
                "priority": "high",
                "sla_status": "warning",
            },
            {
                "id": "APR-002",
                "workflow_id": "WF-20260119002",
                "workflow_name": "Document Approval",
                "step_name": "Quality Review",
                "entity_type": "document",
                "entity_id": "DOC-POL-012",
                "entity_title": "Updated Safety Policy v2.1",
                "requested_at": "2026-01-18T15:00:00Z",
                "due_at": "2026-01-20T15:00:00Z",
                "priority": "normal",
                "sla_status": "ok",
            },
        ]

    def approve(
        self,
        approval_id: str,
        user_id: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Approve an approval request."""
        return {
            "approval_id": approval_id,
            "status": "approved",
            "approved_by": user_id,
            "notes": notes,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def reject(
        self,
        approval_id: str,
        user_id: int,
        reason: str,
    ) -> Dict[str, Any]:
        """Reject an approval request."""
        return {
            "approval_id": approval_id,
            "status": "rejected",
            "rejected_by": user_id,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def bulk_approve(
        self,
        approval_ids: List[str],
        user_id: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Bulk approve multiple requests."""
        results = []
        for approval_id in approval_ids:
            results.append(self.approve(approval_id, user_id, notes))

        return {
            "processed": len(results),
            "successful": len(results),
            "failed": 0,
            "results": results,
        }

    # ==================== Escalation ====================

    def check_escalations(self) -> List[Dict[str, Any]]:
        """Check for workflows that need escalation."""
        # In production, would query database for SLA breaches
        escalations = []
        now = datetime.utcnow()

        # Mock escalation data
        mock_workflows = [
            {
                "id": "WF-20260118001",
                "template": "CAPA",
                "sla_due_at": now - timedelta(hours=2),
                "current_step": "Action Plan Review",
                "priority": "normal",
            }
        ]

        for wf in mock_workflows:
            if wf["sla_due_at"] < now:
                escalations.append(
                    {
                        "workflow_id": wf["id"],
                        "reason": "SLA breach",
                        "hours_overdue": int((now - wf["sla_due_at"]).total_seconds() / 3600),
                        "current_step": wf["current_step"],
                        "recommended_action": "Escalate to Operations Director",
                    }
                )

        return escalations

    def escalate(
        self,
        workflow_id: str,
        escalate_to: int,
        reason: str,
        new_priority: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Escalate a workflow."""
        return {
            "workflow_id": workflow_id,
            "escalated_to": escalate_to,
            "reason": reason,
            "new_priority": new_priority or "high",
            "escalated_at": datetime.utcnow().isoformat(),
        }

    # ==================== Delegation ====================

    def set_delegation(
        self,
        user_id: int,
        delegate_id: int,
        start_date: datetime,
        end_date: datetime,
        reason: Optional[str] = None,
        workflow_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Set up out-of-office delegation."""
        return {
            "id": f"DEL-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "user_id": user_id,
            "delegate_id": delegate_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "reason": reason,
            "workflow_types": workflow_types or ["all"],
            "status": "active",
        }

    def get_active_delegations(self, user_id: int) -> List[Dict[str, Any]]:
        """Get active delegations for a user."""
        return [
            {
                "id": "DEL-20260115001",
                "delegate_id": 5,
                "delegate_name": "Jane Smith",
                "start_date": "2026-01-20T00:00:00Z",
                "end_date": "2026-01-27T23:59:59Z",
                "reason": "Annual leave",
                "status": "scheduled",
            }
        ]

    # ==================== Routing ====================

    def get_routing_rules(self, entity_type: str) -> List[Dict[str, Any]]:
        """Get routing rules for an entity type."""
        rules = {
            "incident": [
                {
                    "id": "RR-001",
                    "condition": {"severity": "critical"},
                    "route_to_role": "safety_director",
                    "priority": "critical",
                },
                {
                    "id": "RR-002",
                    "condition": {"severity": "major"},
                    "route_to_role": "safety_manager",
                    "priority": "high",
                },
                {
                    "id": "RR-003",
                    "condition": {"type": "environmental"},
                    "route_to_role": "environmental_manager",
                    "priority": "high",
                },
            ],
            "complaint": [
                {
                    "id": "RR-004",
                    "condition": {"severity": "high"},
                    "route_to_role": "customer_services_manager",
                    "priority": "high",
                },
            ],
        }
        return rules.get(entity_type, [])

    def route_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Route an entity based on configured rules."""
        rules = self.get_routing_rules(entity_type)

        for rule in rules:
            if self._matches_condition(entity_data, rule["condition"]):
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "matched_rule": rule["id"],
                    "routed_to_role": rule["route_to_role"],
                    "priority": rule["priority"],
                }

        # Default routing
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "matched_rule": None,
            "routed_to_role": "default_handler",
            "priority": "normal",
        }

    def _matches_condition(self, entity_data: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """Check if entity matches a routing condition."""
        for key, value in condition.items():
            if key not in entity_data:
                return False
            if isinstance(value, list):
                if entity_data[key] not in value:
                    return False
            elif entity_data[key] != value:
                return False
        return True

    # ==================== Statistics ====================

    def get_workflow_stats(self) -> Dict[str, Any]:
        """Get workflow statistics."""
        return {
            "active_workflows": 23,
            "pending_approvals": 12,
            "overdue": 3,
            "completed_today": 8,
            "completed_this_week": 45,
            "average_completion_time_hours": 18.5,
            "sla_compliance_rate": 94.2,
            "by_template": {
                "RIDDOR": {"active": 2, "completed": 15, "avg_hours": 22},
                "CAPA": {"active": 8, "completed": 42, "avg_hours": 120},
                "NCR": {"active": 5, "completed": 28, "avg_hours": 48},
                "DOCUMENT_APPROVAL": {"active": 8, "completed": 156, "avg_hours": 24},
            },
            "by_priority": {
                "critical": 2,
                "high": 5,
                "normal": 14,
                "low": 2,
            },
        }


# Singleton instance
workflow_engine = WorkflowEngine()
