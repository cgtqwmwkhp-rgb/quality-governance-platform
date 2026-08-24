"""Reviewable Assist tool catalogue — permissions are string literals.

Adding a tool is a diff that must declare ``required_permission`` (or an
``auth_only_reason``). The authz extraction resolver reads this tuple so the
permission catalogue test fails when a new token is not enforced.
"""

from __future__ import annotations

from typing import Optional

from src.domain.services.assist.types import AssistTool

#: Intent-name tools registered for CORE-01. Planner (PLAN-03) will select from
#: this set; detection maps NL → ``name`` today.
ASSIST_TOOLS: tuple[AssistTool, ...] = (
    AssistTool(
        name="incident_count",
        module="incident",
        description="Count incidents on the tenant register",
        required_permission="incident:read",
    ),
    AssistTool(
        name="incident_closed_count",
        module="incident",
        description="Count closed incidents",
        required_permission="incident:read",
    ),
    AssistTool(
        name="incident_injury_category",
        module="incident",
        description="Incident injury / manual-handling category breakdown",
        required_permission="incident:read",
    ),
    AssistTool(
        name="near_miss_count",
        module="near_miss",
        description="Count near misses",
        required_permission="near_miss:read",
    ),
    AssistTool(
        name="complaint_count",
        module="complaint",
        description="Count complaints",
        required_permission="complaint:read",
    ),
    AssistTool(
        name="overdue_actions",
        module="action",
        description="List overdue actions",
        required_permission="action:read",
    ),
    AssistTool(
        name="compliance_overdue",
        module="compliance_schedule",
        description="Count overdue compliance obligations",
        required_permission="compliance_schedule:read",
    ),
    AssistTool(
        name="compliance_due_soon",
        module="compliance_schedule",
        description="Count compliance obligations due soon",
        required_permission="compliance_schedule:read",
    ),
    AssistTool(
        name="vehicle_check_top_failures",
        module="vehicle_defect",
        description="Top failed van / vehicle checklist fields by defect count",
        required_permission=None,
        auth_only_reason=(
            "/api/v1/vehicles and vehicle checklist analytics take CurrentUser " "with no permission dependency today"
        ),
    ),
    AssistTool(
        name="vehicle_check_defect_summary",
        module="vehicle_defect",
        description="Open vehicle-check defects by priority (P1–P3)",
        required_permission=None,
        auth_only_reason=(
            "/api/v1/vehicles and vehicle checklist analytics take CurrentUser " "with no permission dependency today"
        ),
    ),
)


def get_assist_tool(name: str) -> Optional[AssistTool]:
    """Lookup by tool / intent name, or None."""
    key = (name or "").strip()
    for tool in ASSIST_TOOLS:
        if tool.name == key:
            return tool
    return None


def validate_assist_registry() -> None:
    """Fail fast on registry contract violations (imported by tests / startup)."""
    names: set[str] = set()
    for tool in ASSIST_TOOLS:
        if tool.name in names:
            raise ValueError(f"Duplicate AssistTool name: {tool.name}")
        names.add(tool.name)
        if tool.required_permission is None:
            if not (tool.auth_only_reason or "").strip():
                raise ValueError(f"AssistTool {tool.name} is auth-only without auth_only_reason")
        elif (tool.auth_only_reason or "").strip():
            raise ValueError(f"AssistTool {tool.name} has both required_permission and auth_only_reason")


validate_assist_registry()


__all__ = [
    "ASSIST_TOOLS",
    "get_assist_tool",
    "validate_assist_registry",
]
