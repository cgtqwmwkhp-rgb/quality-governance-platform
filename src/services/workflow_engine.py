"""Workflow Engine Service.

Evaluates conditions, executes actions, manages escalations,
and monitors SLAs across all modules.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.workflow_rules import (
    ActionType,
    EntityType,
    EscalationLevel,
    RuleExecution,
    SLAConfiguration,
    SLATracking,
    TriggerEvent,
    WorkflowRule,
)

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """Evaluates rule conditions against entity data."""

    OPERATORS = {
        "equals": lambda a, b: a == b,
        "not_equals": lambda a, b: a != b,
        "contains": lambda a, b: b in a if a else False,
        "not_contains": lambda a, b: b not in a if a else True,
        "starts_with": lambda a, b: a.startswith(b) if a else False,
        "ends_with": lambda a, b: a.endswith(b) if a else False,
        "greater_than": lambda a, b: a > b if a is not None else False,
        "less_than": lambda a, b: a < b if a is not None else False,
        "greater_or_equal": lambda a, b: a >= b if a is not None else False,
        "less_or_equal": lambda a, b: a <= b if a is not None else False,
        "in": lambda a, b: a in b if isinstance(b, list) else a == b,
        "not_in": lambda a, b: a not in b if isinstance(b, list) else a != b,
        "is_empty": lambda a, b: not a,
        "is_not_empty": lambda a, b: bool(a),
        "is_null": lambda a, b: a is None,
        "is_not_null": lambda a, b: a is not None,
    }

    @classmethod
    def evaluate(cls, conditions: Optional[Dict], entity_data: Dict[str, Any]) -> bool:
        """Evaluate conditions against entity data.

        Args:
            conditions: Condition definition (JSON structure)
            entity_data: Entity fields as dictionary

        Returns:
            True if conditions are met, False otherwise
        """
        if not conditions:
            return True  # No conditions = always match

        # Handle logical operators
        if "and" in conditions:
            return all(cls.evaluate(c, entity_data) for c in conditions["and"])

        if "or" in conditions:
            return any(cls.evaluate(c, entity_data) for c in conditions["or"])

        if "not" in conditions:
            return not cls.evaluate(conditions["not"], entity_data)

        # Handle simple condition
        field = conditions.get("field")
        operator = conditions.get("operator")
        value = conditions.get("value")

        if not field or not operator:
            logger.warning(f"Invalid condition structure: {conditions}")
            return False

        # Get field value (supports nested fields with dot notation)
        entity_value = cls._get_nested_value(entity_data, field)

        # Get operator function
        op_func = cls.OPERATORS.get(operator)
        if not op_func:
            logger.warning(f"Unknown operator: {operator}")
            return False

        try:
            return op_func(entity_value, value)
        except Exception as e:
            logger.error(f"Error evaluating condition: {e}", exc_info=True)
            return False

    @staticmethod
    def _get_nested_value(data: Dict, field: str) -> Any:
        """Get value from nested dictionary using dot notation."""
        keys = field.split(".")
        value: Any = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value


class ActionExecutor:
    """Executes workflow actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(
        self,
        action_type: ActionType,
        action_config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an action.

        Args:
            action_type: Type of action to execute
            action_config: Configuration for the action
            entity_type: Type of entity being processed
            entity_id: ID of the entity
            entity_data: Entity data dictionary

        Returns:
            Dict with action result
        """
        executor_method = getattr(self, f"_execute_{action_type.value}", None)
        if not executor_method:
            logger.warning(f"No executor for action type: {action_type}")
            return {"success": False, "error": f"Unknown action type: {action_type}"}

        try:
            result = await executor_method(action_config, entity_type, entity_id, entity_data)
            return {"success": True, **result}
        except Exception as e:
            logger.error(f"Error executing action {action_type}: {e}")
            return {"success": False, "error": str(e)}

    async def _execute_send_email(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Queue email notification via Celery email tasks."""
        from src.infrastructure.tasks.email_tasks import send_bulk_email, send_email

        template = config.get("template", "default")
        recipients = config.get("recipients") or config.get("to") or []
        if isinstance(recipients, str):
            recipients = [recipients]
        recipients = [str(r).strip() for r in recipients if str(r).strip()]
        subject = config.get("subject", f"Notification for {entity_type.value} #{entity_id}")
        body = (
            config.get("body")
            or config.get("message")
            or (f"{subject}\n\nEntity: {entity_type.value} #{entity_id}\nTemplate: {template}")
        )
        html = bool(config.get("html", False))
        use_bulk = bool(config.get("use_bulk", False))

        if not recipients:
            raise ValueError("send_email action requires at least one recipient")

        try:
            if use_bulk and len(recipients) > 1:
                async_result = send_bulk_email.delay(recipients, subject, body)
                task_ids = [async_result.id]
            elif len(recipients) == 1:
                async_result = send_email.delay(recipients[0], subject, body, html)
                task_ids = [async_result.id]
            else:
                task_ids = []
                for recipient in recipients:
                    async_result = send_email.delay(recipient, subject, body, html)
                    task_ids.append(async_result.id)
        except Exception as exc:
            logger.error(
                "Failed to enqueue workflow email template=%s recipients=%s: %s",
                template,
                recipients,
                exc,
            )
            raise RuntimeError(f"Failed to enqueue email: {exc}") from exc

        logger.info(
            "Queued workflow email template=%s recipients=%s subject=%s task_ids=%s",
            template,
            recipients,
            subject,
            task_ids,
        )
        return {
            "action": "send_email",
            "template": template,
            "recipients": recipients,
            "subject": subject,
            "queued": True,
            "task_ids": task_ids,
            "task_id": task_ids[0] if len(task_ids) == 1 else None,
        }

    async def _execute_send_sms(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Send SMS notification."""
        # Future: integrate Twilio or similar SMS provider
        phone = config.get("phone")
        message = config.get("message", f"Alert for {entity_type.value} #{entity_id}")

        logger.info(f"Would send SMS: phone={phone}, message={message}")

        return {
            "action": "send_sms",
            "phone": phone,
            "queued": True,
        }

    async def _execute_assign_to_user(
        self,
        config: Dict[str, Any],
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Assign entity to a specific user."""
        user_id = config.get("user_id")

        model = self._get_model_for_entity(entity_type)
        if model is not None:
            from sqlalchemy import update

            await self.db.execute(
                update(model).where(model.id == entity_id).values(assigned_to_id=user_id)  # type: ignore[attr-defined]
            )
            await self.db.commit()

        return {
            "action": "assign_to_user",
            "user_id": user_id,
            "completed": True,
        }

    async def _execute_assign_to_role(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Assign entity to a user with a specific role."""
        role = config.get("role")
        department = config.get("department", entity_data.get("department"))

        # Find a user with the specified role
        # Future: implement user lookup by role from users table
        logger.info(f"Would assign to role: {role} in department: {department}")

        return {
            "action": "assign_to_role",
            "role": role,
            "department": department,
            "pending_user_lookup": True,
        }

    async def _execute_change_status(
        self,
        config: Dict[str, Any],
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Change entity status."""
        new_status = config.get("new_status")

        model = self._get_model_for_entity(entity_type)
        if model is not None:
            from sqlalchemy import update

            await self.db.execute(
                update(model).where(model.id == entity_id).values(status=new_status)  # type: ignore[attr-defined]
            )
            await self.db.commit()

        return {
            "action": "change_status",
            "new_status": new_status,
            "completed": True,
        }

    async def _execute_change_priority(
        self,
        config: Dict[str, Any],
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Change entity priority."""
        new_priority = config.get("new_priority")

        model = self._get_model_for_entity(entity_type)
        if model is not None:
            from sqlalchemy import update

            await self.db.execute(
                update(model).where(model.id == entity_id).values(priority=new_priority)  # type: ignore[attr-defined]
            )
            await self.db.commit()

        return {
            "action": "change_priority",
            "new_priority": new_priority,
            "completed": True,
        }

    async def _execute_escalate(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Escalate entity to next level."""
        current_level = entity_data.get("escalation_level", 0)
        new_level = current_level + 1

        # Get escalation configuration
        result = await self.db.execute(
            select(EscalationLevel).where(
                and_(
                    EscalationLevel.entity_type == entity_type,
                    EscalationLevel.level == new_level,
                    EscalationLevel.is_active == True,
                )
            )
        )
        escalation = result.scalar_one_or_none()

        if escalation:
            model = self._get_model_for_entity(entity_type)
            if model is not None:
                from sqlalchemy import update

                await self.db.execute(
                    update(model)
                    .where(model.id == entity_id)  # type: ignore[attr-defined]
                    .values(
                        escalation_level=new_level,
                        status="escalated",
                    )
                )
                await self.db.commit()

            # Send escalation notification
            if escalation.escalate_to_user_id:
                await self._execute_assign_to_user(
                    {"user_id": escalation.escalate_to_user_id},
                    entity_type,
                    entity_id,
                    entity_data,
                )

            return {
                "action": "escalate",
                "new_level": new_level,
                "escalate_to_role": escalation.escalate_to_role,
                "completed": True,
            }

        return {
            "action": "escalate",
            "new_level": new_level,
            "completed": False,
            "reason": "No escalation level configured",
        }

    async def _execute_update_risk_score(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Update associated risk score."""
        # Trigger risk score recalculation
        risk_id = config.get("risk_id") or entity_data.get("risk_id")
        score_adjustment = config.get("score_adjustment", 0)

        logger.info(f"Would update risk score: risk_id={risk_id}, adjustment={score_adjustment}")

        return {
            "action": "update_risk_score",
            "risk_id": risk_id,
            "adjustment": score_adjustment,
        }

    async def _execute_log_audit_event(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Log an audit event."""
        event_type = config.get("event_type", "workflow_action")
        details = config.get("details", {})

        # Use audit service when available
        logger.info(f"Audit event: {event_type} for {entity_type.value} #{entity_id}")

        return {
            "action": "log_audit_event",
            "event_type": event_type,
            "logged": True,
        }

    async def _execute_create_task(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Create a follow-up task."""
        title = config.get("title", f"Follow-up for {entity_type.value} #{entity_id}")
        description = config.get("description", "")
        due_days = config.get("due_days", 7)
        assign_to = config.get("assign_to")

        # Future: integrate with external task management system
        logger.info(f"Would create task: {title}, due in {due_days} days")

        return {
            "action": "create_task",
            "title": title,
            "due_days": due_days,
            "created": True,
        }

    async def _execute_webhook(
        self,
        config: Dict,
        entity_type: EntityType,
        entity_id: int,
        entity_data: Dict,
    ) -> Dict:
        """Queue external webhook delivery via Celery + httpx."""
        from src.infrastructure.tasks.webhook_tasks import deliver_webhook

        url = config.get("url")
        if not url:
            raise ValueError("webhook action requires a url")

        method = config.get("method", "POST")
        headers = config.get("headers") or {}
        body = config.get("body")
        payload = config.get("payload")
        timeout = config.get("timeout")

        try:
            async_result = deliver_webhook.delay(
                url=url,
                method=method,
                headers=headers,
                entity_type=entity_type.value,
                entity_id=entity_id,
                body=body if isinstance(body, dict) else None,
                payload=payload if isinstance(payload, dict) else None,
                timeout=timeout,
            )
        except Exception as exc:
            logger.error("Failed to enqueue webhook url=%s method=%s: %s", url, method, exc)
            raise RuntimeError(f"Failed to enqueue webhook: {exc}") from exc

        logger.info(
            "Queued workflow webhook method=%s url=%s entity=%s#%s task_id=%s",
            method,
            url,
            entity_type.value,
            entity_id,
            async_result.id,
        )
        return {
            "action": "webhook",
            "url": url,
            "method": method,
            "queued": True,
            "task_id": async_result.id,
        }

    def _get_model_for_entity(self, entity_type: EntityType) -> Optional[Type[Any]]:
        """Get SQLAlchemy model for entity type."""
        from src.domain.models.complaint import Complaint
        from src.domain.models.incident import Incident
        from src.domain.models.near_miss import NearMiss
        from src.domain.models.rta import RTA

        models: Dict[EntityType, Type[Any]] = {
            EntityType.INCIDENT: Incident,
            EntityType.NEAR_MISS: NearMiss,
            EntityType.COMPLAINT: Complaint,
            EntityType.RTA: RTA,
        }
        return models.get(entity_type)


class WorkflowEngine:
    """Main workflow engine service."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.condition_evaluator = ConditionEvaluator()
        self.action_executor = ActionExecutor(db)

    async def process_event(
        self,
        entity_type: EntityType,
        entity_id: int,
        trigger_event: TriggerEvent,
        entity_data: Dict[str, Any],
        old_data: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Process a trigger event and execute matching rules.

        Args:
            entity_type: Type of entity
            entity_id: Entity ID
            trigger_event: Event that occurred
            entity_data: Current entity data
            old_data: Previous entity data (for updates)

        Returns:
            List of execution results
        """
        # Get applicable rules
        rules = await self._get_matching_rules(entity_type, trigger_event, entity_data)

        results = []
        for rule in rules:
            # Check conditions
            if not self.condition_evaluator.evaluate(rule.conditions, entity_data):
                continue

            # Execute action
            action_result = await self.action_executor.execute(
                rule.action_type,
                rule.action_config,
                entity_type,
                entity_id,
                entity_data,
            )

            # Log execution
            execution = RuleExecution(
                rule_id=rule.id,
                entity_type=entity_type,
                entity_id=entity_id,
                trigger_event=trigger_event,
                executed_at=datetime.now(timezone.utc),
                success=action_result.get("success", False),
                error_message=action_result.get("error"),
                action_taken=f"{rule.action_type.value}: {rule.name}",
                action_result=action_result,
            )
            self.db.add(execution)

            results.append(
                {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "action_type": rule.action_type.value,
                    **action_result,
                }
            )

            # Stop processing if rule indicates
            if rule.stop_processing:
                break

        await self.db.commit()
        return results

    async def _get_matching_rules(
        self,
        entity_type: EntityType,
        trigger_event: TriggerEvent,
        entity_data: Dict[str, Any],
    ) -> List[WorkflowRule]:
        """Get rules that match the entity type and trigger event."""
        query = (
            select(WorkflowRule)
            .where(
                and_(
                    WorkflowRule.entity_type == entity_type,
                    WorkflowRule.trigger_event == trigger_event,
                    WorkflowRule.is_active == True,
                )
            )
            .order_by(WorkflowRule.priority)
        )

        # Filter by department/contract if specified
        department = entity_data.get("department")
        contract = entity_data.get("contract")

        result = await self.db.execute(query)
        rules = result.scalars().all()

        # Filter rules by scope
        matching_rules = []
        for rule in rules:
            if rule.department and rule.department != department:
                continue
            if rule.contract and rule.contract != contract:
                continue
            matching_rules.append(rule)

        return matching_rules

    async def check_escalations(self) -> List[Dict[str, Any]]:
        """Check and process pending escalations.

        This should be called periodically (e.g., every 5 minutes) by a scheduler.
        """
        results: list[dict[str, Any]] = []

        # Get escalation rules with time-based triggers
        query = select(WorkflowRule).where(
            and_(
                WorkflowRule.rule_type == "escalation",
                WorkflowRule.is_active == True,
                WorkflowRule.delay_hours.isnot(None),
            )
        )

        result = await self.db.execute(query)
        rules = result.scalars().all()

        for rule in rules:
            # Find entities that need escalation
            model = self.action_executor._get_model_for_entity(rule.entity_type)
            if not model:
                continue

            threshold = datetime.now(timezone.utc) - timedelta(hours=float(rule.delay_hours or 0))
            delay_field = rule.delay_from_field or "created_at"

            # This is a simplified example - real implementation would be more sophisticated
            # Find entities where the delay field is older than threshold
            # and conditions match

            logger.info(f"Checking escalation rule: {rule.name}")

        return results

    async def check_sla_breaches(self) -> List[Dict[str, Any]]:
        """Check for SLA warnings and breaches.

        This should be called periodically by a scheduler.
        """
        now = datetime.now(timezone.utc)
        results = []

        # Check for SLA warnings
        warning_query = select(SLATracking).where(
            and_(
                SLATracking.warning_sent == False,
                SLATracking.is_breached == False,
                SLATracking.resolved_at.is_(None),
                SLATracking.is_paused == False,
            )
        )

        result = await self.db.execute(warning_query)
        trackings = result.scalars().all()

        for tracking in trackings:
            # Get SLA config for warning threshold
            config_result = await self.db.execute(
                select(SLAConfiguration).where(SLAConfiguration.id == tracking.sla_config_id)
            )
            config = config_result.scalar_one_or_none()

            if not config:
                continue

            # Calculate warning time
            total_duration = (tracking.resolution_due - tracking.started_at).total_seconds() / 3600
            elapsed = (now - tracking.started_at).total_seconds() / 3600
            percent_elapsed = (elapsed / total_duration) * 100 if total_duration > 0 else 100

            if percent_elapsed >= config.warning_threshold_percent and not tracking.warning_sent:
                # Send warning
                await self.process_event(
                    tracking.entity_type,
                    tracking.entity_id,
                    TriggerEvent.SLA_WARNING,
                    {
                        "sla_tracking_id": tracking.id,
                        "percent_elapsed": percent_elapsed,
                    },
                )
                tracking.warning_sent = True
                results.append(
                    {
                        "entity_type": tracking.entity_type.value,
                        "entity_id": tracking.entity_id,
                        "event": "sla_warning",
                        "percent_elapsed": percent_elapsed,
                    }
                )

            # Check for breach
            if now > tracking.resolution_due and not tracking.is_breached:
                await self.process_event(
                    tracking.entity_type,
                    tracking.entity_id,
                    TriggerEvent.SLA_BREACH,
                    {"sla_tracking_id": tracking.id},
                )
                tracking.is_breached = True
                tracking.breach_sent = True
                results.append(
                    {
                        "entity_type": tracking.entity_type.value,
                        "entity_id": tracking.entity_id,
                        "event": "sla_breach",
                    }
                )

        await self.db.commit()
        return results


class SLAService:
    """Service for managing SLA tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_tracking(
        self,
        entity_type: EntityType,
        entity_id: int,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        department: Optional[str] = None,
        contract: Optional[str] = None,
    ) -> Optional[SLATracking]:
        """Start SLA tracking for an entity."""
        # Find matching SLA configuration
        config = await self._find_matching_config(entity_type, priority, category, department, contract)

        if not config:
            logger.info(f"No SLA config found for {entity_type.value}")
            return None

        now = datetime.now(timezone.utc)

        # Calculate due times
        acknowledgment_due = None
        response_due = None

        if config.acknowledgment_hours:
            acknowledgment_due = self._calculate_due_time(now, config.acknowledgment_hours, config)

        if config.response_hours:
            response_due = self._calculate_due_time(now, config.response_hours, config)

        resolution_due = self._calculate_due_time(now, config.resolution_hours, config)

        tracking = SLATracking(
            entity_type=entity_type,
            entity_id=entity_id,
            sla_config_id=config.id,
            started_at=now,
            acknowledgment_due=acknowledgment_due,
            response_due=response_due,
            resolution_due=resolution_due,
        )

        self.db.add(tracking)
        await self.db.commit()
        await self.db.refresh(tracking)

        return tracking

    async def mark_acknowledged(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        """Mark entity as acknowledged."""
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.acknowledged_at:
            tracking.acknowledged_at = datetime.now(timezone.utc)
            tracking.acknowledgment_met = (
                tracking.acknowledged_at <= tracking.acknowledgment_due if tracking.acknowledgment_due else True
            )
            await self.db.commit()
        return tracking

    async def mark_responded(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        """Mark entity as responded to."""
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.responded_at:
            tracking.responded_at = datetime.now(timezone.utc)
            tracking.response_met = tracking.responded_at <= tracking.response_due if tracking.response_due else True
            await self.db.commit()
        return tracking

    async def mark_resolved(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        """Mark entity as resolved."""
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.resolved_at:
            tracking.resolved_at = datetime.now(timezone.utc)
            tracking.resolution_met = tracking.resolved_at <= tracking.resolution_due
            await self.db.commit()
        return tracking

    async def pause_tracking(self, entity_type: EntityType, entity_id: int, reason: str = "") -> Optional[SLATracking]:
        """Pause SLA tracking (e.g., waiting for customer)."""
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and not tracking.is_paused:
            tracking.is_paused = True
            tracking.paused_at = datetime.now(timezone.utc)
            await self.db.commit()
        return tracking

    async def resume_tracking(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        """Resume SLA tracking."""
        tracking = await self._get_tracking(entity_type, entity_id)
        if tracking and tracking.is_paused and tracking.paused_at is not None:
            paused_duration = (datetime.now(timezone.utc) - tracking.paused_at).total_seconds() / 3600
            tracking.total_paused_hours = (tracking.total_paused_hours or 0) + paused_duration
            tracking.is_paused = False
            tracking.paused_at = None

            # Adjust due times
            adjustment = timedelta(hours=paused_duration)
            if tracking.acknowledgment_due:
                tracking.acknowledgment_due += adjustment
            if tracking.response_due:
                tracking.response_due += adjustment
            tracking.resolution_due += adjustment

            await self.db.commit()
        return tracking

    async def _get_tracking(self, entity_type: EntityType, entity_id: int) -> Optional[SLATracking]:
        """Get SLA tracking for an entity."""
        result = await self.db.execute(
            select(SLATracking)
            .where(
                and_(
                    SLATracking.entity_type == entity_type,
                    SLATracking.entity_id == entity_id,
                )
            )
            .order_by(SLATracking.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_matching_config(
        self,
        entity_type: EntityType,
        priority: Optional[str],
        category: Optional[str],
        department: Optional[str],
        contract: Optional[str],
    ) -> Optional[SLAConfiguration]:
        """Find the most specific matching SLA configuration."""
        query = (
            select(SLAConfiguration)
            .where(
                and_(
                    SLAConfiguration.entity_type == entity_type,
                    SLAConfiguration.is_active == True,
                )
            )
            .order_by(SLAConfiguration.match_priority.desc())
        )

        result = await self.db.execute(query)
        configs = result.scalars().all()

        # Find best match
        for config in configs:
            matches = True
            if config.priority and config.priority != priority:
                matches = False
            if config.category and config.category != category:
                matches = False
            if config.department and config.department != department:
                matches = False
            if config.contract and config.contract != contract:
                matches = False

            if matches:
                return config

        # Return first config for entity type if no specific match
        return configs[0] if configs else None

    def _calculate_due_time(
        self,
        start: datetime,
        hours: float,
        config: SLAConfiguration,
    ) -> datetime:
        """Calculate due time considering business hours."""
        if not config.business_hours_only:
            return start + timedelta(hours=hours)

        # Business hours calculation
        current = start
        remaining_hours = hours

        while remaining_hours > 0:
            # Skip to business hours if outside
            if current.hour < config.business_start_hour:
                current = current.replace(hour=config.business_start_hour, minute=0, second=0)
            elif current.hour >= config.business_end_hour:
                current = current + timedelta(days=1)
                current = current.replace(hour=config.business_start_hour, minute=0, second=0)

            # Skip weekends
            if config.exclude_weekends and current.weekday() >= 5:
                days_until_monday = 7 - current.weekday()
                current = current + timedelta(days=days_until_monday)
                current = current.replace(hour=config.business_start_hour, minute=0, second=0)
                continue

            # Calculate hours available today
            hours_today = config.business_end_hour - current.hour
            if remaining_hours <= hours_today:
                current = current + timedelta(hours=remaining_hours)
                remaining_hours = 0
            else:
                remaining_hours -= hours_today
                current = current + timedelta(days=1)
                current = current.replace(hour=config.business_start_hour, minute=0, second=0)

        return current
