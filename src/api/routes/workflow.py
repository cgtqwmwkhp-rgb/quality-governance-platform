"""Workflow Engine API Routes.

Provides CRUD operations for workflow rules, SLA configurations,
escalation levels, and status checking.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession
from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.api.schemas.workflow import (
    EscalationLevelCreate,
    EscalationLevelListResponse,
    EscalationLevelResponse,
    EscalationLevelUpdate,
    RuleExecutionListResponse,
    RuleExecutionResponse,
    SLAConfigurationCreate,
    SLAConfigurationListResponse,
    SLAConfigurationResponse,
    SLAConfigurationUpdate,
    SLAStatusSummary,
    SLATrackingResponse,
    WorkflowRuleCreate,
    WorkflowRuleListResponse,
    WorkflowRuleResponse,
    WorkflowRuleUpdate,
)
from src.domain.models.workflow_rules import (
    EntityType,
    EscalationLevel,
    RuleExecution,
    SLAConfiguration,
    SLATracking,
    WorkflowRule,
)
from src.domain.services.workflow_engine import RuleEvaluator, SLAService

router = APIRouter(prefix="/workflow", tags=["Workflow Engine"])


# =============================================================================
# Workflow Rules
# =============================================================================


@router.get("/rules", response_model=WorkflowRuleListResponse)
async def list_workflow_rules(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    rule_type: Optional[str] = Query(None, description="Filter by rule type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List workflow rules with optional filtering."""
    query = select(WorkflowRule).where(WorkflowRule.tenant_id == current_user.tenant_id)

    filters = []
    if entity_type:
        filters.append(WorkflowRule.entity_type == entity_type)
    if rule_type:
        filters.append(WorkflowRule.rule_type == rule_type)
    if is_active is not None:
        filters.append(WorkflowRule.is_active == is_active)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(WorkflowRule.priority, WorkflowRule.name)

    return await paginate(db, query, params)


@router.post("/rules", response_model=WorkflowRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_rule(
    rule_data: WorkflowRuleCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new workflow rule."""
    rule = WorkflowRule(
        **rule_data.dict(),
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.get("id"),
        created_by=current_user.get("email"),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return WorkflowRuleResponse.from_orm(rule)


@router.get("/rules/{rule_id}", response_model=WorkflowRuleResponse)
async def get_workflow_rule(
    rule_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific workflow rule."""
    rule = await get_or_404(db, WorkflowRule, rule_id, tenant_id=current_user.tenant_id)
    return WorkflowRuleResponse.from_orm(rule)


@router.patch("/rules/{rule_id}", response_model=WorkflowRuleResponse)
async def update_workflow_rule(
    rule_id: int,
    rule_data: WorkflowRuleUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update a workflow rule."""
    rule = await get_or_404(db, WorkflowRule, rule_id, tenant_id=current_user.tenant_id)
    apply_updates(rule, rule_data)
    rule.updated_by = current_user.get("email")

    await db.commit()
    await db.refresh(rule)
    return WorkflowRuleResponse.from_orm(rule)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_rule(
    rule_id: int,
    current_user: CurrentSuperuser,
    db: DbSession,
):
    """Delete a workflow rule (superuser only)."""
    rule = await get_or_404(db, WorkflowRule, rule_id, tenant_id=current_user.tenant_id)
    await db.delete(rule)
    await db.commit()


@router.get("/rules/{rule_id}/executions", response_model=RuleExecutionListResponse)
async def get_rule_executions(
    rule_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
):
    """Get execution history for a workflow rule."""
    await get_or_404(db, WorkflowRule, rule_id, tenant_id=current_user.tenant_id)

    result = await db.execute(
        select(RuleExecution)
        .where(RuleExecution.rule_id == rule_id)
        .order_by(RuleExecution.executed_at.desc())
        .limit(limit)
    )
    executions = result.scalars().all()

    count_result = await db.execute(select(func.count(RuleExecution.id)).where(RuleExecution.rule_id == rule_id))
    total = count_result.scalar()

    return RuleExecutionListResponse(
        items=[RuleExecutionResponse.from_orm(e) for e in executions],
        total=total,
    )


# =============================================================================
# SLA Configurations
# =============================================================================


@router.get("/sla-configs", response_model=SLAConfigurationListResponse)
async def list_sla_configurations(
    db: DbSession,
    current_user: CurrentUser,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List SLA configurations."""
    query = select(SLAConfiguration).where(SLAConfiguration.tenant_id == current_user.tenant_id)

    filters = []
    if entity_type:
        filters.append(SLAConfiguration.entity_type == entity_type)
    if is_active is not None:
        filters.append(SLAConfiguration.is_active == is_active)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(SLAConfiguration.entity_type, SLAConfiguration.match_priority.desc())

    result = await db.execute(query)
    configs = result.scalars().all()

    return SLAConfigurationListResponse(
        items=[SLAConfigurationResponse.from_orm(c) for c in configs],
        total=len(configs),
    )


@router.post("/sla-configs", response_model=SLAConfigurationResponse, status_code=status.HTTP_201_CREATED)
async def create_sla_configuration(
    config_data: SLAConfigurationCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new SLA configuration."""
    config = SLAConfiguration(
        **config_data.dict(),
        tenant_id=current_user.tenant_id,
        created_by=current_user.get("email"),
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return SLAConfigurationResponse.from_orm(config)


@router.get("/sla-configs/{config_id}", response_model=SLAConfigurationResponse)
async def get_sla_configuration(
    config_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific SLA configuration."""
    config = await get_or_404(db, SLAConfiguration, config_id, tenant_id=current_user.tenant_id)
    return SLAConfigurationResponse.from_orm(config)


@router.patch("/sla-configs/{config_id}", response_model=SLAConfigurationResponse)
async def update_sla_configuration(
    config_id: int,
    config_data: SLAConfigurationUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update an SLA configuration."""
    config = await get_or_404(db, SLAConfiguration, config_id, tenant_id=current_user.tenant_id)
    apply_updates(config, config_data)
    config.updated_by = current_user.get("email")

    await db.commit()
    await db.refresh(config)
    return SLAConfigurationResponse.from_orm(config)


@router.delete("/sla-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sla_configuration(
    config_id: int,
    current_user: CurrentSuperuser,
    db: DbSession,
):
    """Delete an SLA configuration (superuser only)."""
    config = await get_or_404(db, SLAConfiguration, config_id, tenant_id=current_user.tenant_id)
    await db.delete(config)
    await db.commit()


# =============================================================================
# SLA Tracking
# =============================================================================


@router.get("/sla-status/{entity_type}/{entity_id}", response_model=SLAStatusSummary)
async def get_sla_status(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get current SLA status for an entity."""
    from datetime import datetime

    result = await db.execute(
        select(SLATracking)
        .where(
            and_(
                SLATracking.tenant_id == current_user.tenant_id,
                SLATracking.entity_type == entity_type,
                SLATracking.entity_id == entity_id,
            )
        )
        .order_by(SLATracking.created_at.desc())
        .limit(1)
    )
    tracking = result.scalar_one_or_none()

    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA tracking not found for this entity")

    now = datetime.utcnow()

    # Calculate SLA status
    if tracking.resolved_at:
        sla_status = "resolved"
        percent_elapsed = 100.0
        time_remaining = None
    elif tracking.is_breached:
        sla_status = "breached"
        percent_elapsed = 100.0
        time_remaining = None
    else:
        total_duration = (tracking.resolution_due - tracking.started_at).total_seconds() / 3600
        elapsed = (now - tracking.started_at).total_seconds() / 3600
        percent_elapsed = min((elapsed / total_duration) * 100, 100) if total_duration > 0 else 100
        time_remaining = max((tracking.resolution_due - now).total_seconds() / 3600, 0)

        if tracking.warning_sent or percent_elapsed >= 75:
            sla_status = "warning"
        else:
            sla_status = "on_track"

    return SLAStatusSummary(
        entity_type=tracking.entity_type,
        entity_id=tracking.entity_id,
        status=sla_status,
        percent_elapsed=round(percent_elapsed, 1),
        time_remaining_hours=round(time_remaining, 2) if time_remaining else None,
        resolution_due=tracking.resolution_due,
        is_paused=tracking.is_paused,
    )


@router.post("/sla-tracking/{entity_type}/{entity_id}/pause", response_model=SLATrackingResponse)
async def pause_sla_tracking(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Pause SLA tracking for an entity (e.g., waiting for customer response)."""
    sla_service = SLAService(db)
    tracking = await sla_service.pause_tracking(EntityType(entity_type), entity_id)

    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA tracking not found")

    return SLATrackingResponse.from_orm(tracking)


@router.post("/sla-tracking/{entity_type}/{entity_id}/resume", response_model=SLATrackingResponse)
async def resume_sla_tracking(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Resume paused SLA tracking."""
    sla_service = SLAService(db)
    tracking = await sla_service.resume_tracking(EntityType(entity_type), entity_id)

    if not tracking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SLA tracking not found")

    return SLATrackingResponse.from_orm(tracking)


# =============================================================================
# Escalation Levels
# =============================================================================


@router.get("/escalation-levels", response_model=EscalationLevelListResponse)
async def list_escalation_levels(
    db: DbSession,
    current_user: CurrentUser,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
):
    """List escalation levels."""
    query = select(EscalationLevel).where(EscalationLevel.tenant_id == current_user.tenant_id)

    filters = []
    if entity_type:
        filters.append(EscalationLevel.entity_type == entity_type)
    if is_active is not None:
        filters.append(EscalationLevel.is_active == is_active)

    if filters:
        query = query.where(and_(*filters))

    query = query.order_by(EscalationLevel.entity_type, EscalationLevel.level)

    result = await db.execute(query)
    levels = result.scalars().all()

    return EscalationLevelListResponse(
        items=[EscalationLevelResponse.from_orm(l) for l in levels],
        total=len(levels),
    )


@router.post("/escalation-levels", response_model=EscalationLevelResponse, status_code=status.HTTP_201_CREATED)
async def create_escalation_level(
    level_data: EscalationLevelCreate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Create a new escalation level."""
    level = EscalationLevel(**level_data.dict(), tenant_id=current_user.tenant_id)
    db.add(level)
    await db.commit()
    await db.refresh(level)
    return EscalationLevelResponse.from_orm(level)


@router.get("/escalation-levels/{level_id}", response_model=EscalationLevelResponse)
async def get_escalation_level(
    level_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific escalation level."""
    level = await get_or_404(db, EscalationLevel, level_id, tenant_id=current_user.tenant_id)
    return EscalationLevelResponse.from_orm(level)


@router.patch("/escalation-levels/{level_id}", response_model=EscalationLevelResponse)
async def update_escalation_level(
    level_id: int,
    level_data: EscalationLevelUpdate,
    db: DbSession,
    current_user: CurrentUser,
):
    """Update an escalation level."""
    level = await get_or_404(db, EscalationLevel, level_id, tenant_id=current_user.tenant_id)
    apply_updates(level, level_data)
    await db.commit()
    await db.refresh(level)
    return EscalationLevelResponse.from_orm(level)


@router.delete("/escalation-levels/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_escalation_level(
    level_id: int,
    current_user: CurrentSuperuser,
    db: DbSession,
):
    """Delete an escalation level (superuser only)."""
    level = await get_or_404(db, EscalationLevel, level_id, tenant_id=current_user.tenant_id)
    await db.delete(level)
    await db.commit()


# =============================================================================
# Manual Triggers
# =============================================================================


@router.post("/trigger-check")
async def trigger_sla_check(
    db: DbSession,
    current_user: CurrentUser,
):
    """Manually trigger SLA checks (normally run by scheduler)."""
    engine = RuleEvaluator(db)

    escalation_results = await engine.check_escalations()
    sla_results = await engine.check_sla_breaches()

    return {
        "message": "SLA and escalation check completed",
        "escalations_processed": len(escalation_results),
        "sla_events": len(sla_results),
        "escalation_details": escalation_results,
        "sla_details": sla_results,
    }
