"""Audit reporting/analytics service.

Provides the reporting-pack aggregates consumed by ``/audits/analytics/*``
routes: a headline summary, dimensional breakdowns (asset type, assessment
mode, template, criticality, customer, location, engineer, week), a CSV
export at run×response grain, and an incomplete-essential-items queue.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditStatus,
    AuditTemplate,
    FindingStatus,
    QuestionCriticality,
    ResponseApplicability,
)
from src.domain.models.asset import AssetType
from src.domain.models.engineer import Engineer
from src.domain.models.location import Location
from src.domain.services.audit_scoring_service import AuditScoringService

SUPPORTED_GROUP_BY = (
    "asset_type",
    "assessment_mode",
    "template",
    "criticality",
    "customer",
    "location",
    "engineer",
    "week",
)


@dataclass
class CriticalQueueItem:
    run_id: int
    run_reference_number: Optional[str]
    template_id: int
    template_name: Optional[str]
    question_id: int
    question_text: str
    reason: str  # "unanswered" | "failed_open_finding"
    finding_id: Optional[int] = None
    finding_status: Optional[str] = None


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _cutoff(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=max(days, 0))


class AuditAnalyticsService:
    """Read-only aggregates over AuditRun/AuditResponse/AuditQuestion."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    async def _essential_compliance_totals(
        self,
        tenant_id: int,
        cutoff: datetime,
        *,
        run_ids: Optional[list[int]] = None,
    ) -> tuple[int, int]:
        """Return (total_applicable_essential_responses, failed_count)."""
        base_where = [
            AuditRun.tenant_id == tenant_id,
            AuditRun.created_at >= cutoff,
            AuditQuestion.criticality == QuestionCriticality.ESSENTIAL.value,
            (AuditResponse.applicability.is_(None))
            | (AuditResponse.applicability == ResponseApplicability.APPLICABLE.value),
        ]
        if run_ids is not None:
            if not run_ids:
                return 0, 0
            base_where.append(AuditResponse.run_id.in_(run_ids))

        total_stmt = (
            select(func.count(AuditResponse.id))
            .join(AuditQuestion, AuditQuestion.id == AuditResponse.question_id)
            .join(AuditRun, AuditRun.id == AuditResponse.run_id)
            .where(*base_where)
        )
        total = int((await self.db.scalar(total_stmt)) or 0)
        if total == 0:
            return 0, 0

        failed_stmt = (
            select(func.count(func.distinct(AuditResponse.id)))
            .join(AuditQuestion, AuditQuestion.id == AuditResponse.question_id)
            .join(AuditRun, AuditRun.id == AuditResponse.run_id)
            .join(
                AuditFinding,
                (AuditFinding.run_id == AuditResponse.run_id) & (AuditFinding.question_id == AuditResponse.question_id),
            )
            .where(*base_where)
        )
        failed = int((await self.db.scalar(failed_stmt)) or 0)
        return total, failed

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def get_summary(
        self,
        tenant_id: int,
        *,
        days: int = 90,
    ) -> dict[str, Any]:
        cutoff = _cutoff(days)
        base_filters = (AuditRun.tenant_id == tenant_id, AuditRun.created_at >= cutoff)

        totals = int((await self.db.scalar(select(func.count()).select_from(AuditRun).where(*base_filters))) or 0)
        completed = int(
            (
                await self.db.scalar(
                    select(func.count())
                    .select_from(AuditRun)
                    .where(*base_filters, AuditRun.status == AuditStatus.COMPLETED.value)
                )
            )
            or 0
        )
        in_progress = int(
            (
                await self.db.scalar(
                    select(func.count())
                    .select_from(AuditRun)
                    .where(*base_filters, AuditRun.status == AuditStatus.IN_PROGRESS.value)
                )
            )
            or 0
        )

        avg_score = await self.db.scalar(
            select(func.avg(AuditRun.score_percentage)).where(
                *base_filters,
                AuditRun.status == AuditStatus.COMPLETED.value,
                AuditRun.score_percentage.is_not(None),
            )
        )
        passed_count = int(
            (
                await self.db.scalar(
                    select(func.count())
                    .select_from(AuditRun)
                    .where(*base_filters, AuditRun.passed.is_(True))
                )
            )
            or 0
        )
        decided_count = int(
            (
                await self.db.scalar(
                    select(func.count())
                    .select_from(AuditRun)
                    .where(*base_filters, AuditRun.passed.is_not(None))
                )
            )
            or 0
        )
        pass_rate = (passed_count / decided_count * 100) if decided_count else 0.0

        essential_total, essential_failed = await self._essential_compliance_totals(tenant_id, cutoff)
        essential_compliance_pct = (
            (1 - (essential_failed / essential_total)) * 100 if essential_total else 100.0
        )

        critical_queue = await self.get_critical_queue(tenant_id)

        return {
            "period_days": days,
            "totals": totals,
            "completed": completed,
            "in_progress": in_progress,
            "avg_score": round(float(avg_score), 2) if avg_score is not None else 0.0,
            "pass_rate": round(pass_rate, 2),
            "essential_compliance_pct": round(essential_compliance_pct, 2),
            "incomplete_critical_count": len(critical_queue),
        }

    # ------------------------------------------------------------------
    # Dimensions
    # ------------------------------------------------------------------

    @staticmethod
    def _dimension_key_label(run: AuditRun, group_by: str) -> tuple[str, str]:
        if group_by == "asset_type":
            if run.asset_type_id is None:
                return "unassigned", "Unassigned"
            asset_type = run.__dict__.get("asset_type")
            label = asset_type.name if asset_type is not None else f"Asset type {run.asset_type_id}"
            return str(run.asset_type_id), label
        if group_by == "assessment_mode":
            mode = run.assessment_mode or "unspecified"
            return mode, mode.replace("_", " ").title()
        if group_by == "template":
            template = run.__dict__.get("template")
            label = template.name if template is not None else f"Template {run.template_id}"
            return str(run.template_id), label
        if group_by == "customer":
            code = run.customer_code or "unspecified"
            return code, code
        if group_by == "location":
            if run.location_id is None:
                return "unassigned", "Unassigned"
            location = run.__dict__.get("run_location")
            label = location.name if location is not None else f"Location {run.location_id}"
            return str(run.location_id), label
        if group_by == "engineer":
            if run.engineer_id is None:
                return "unassigned", "Unassigned"
            engineer = run.__dict__.get("engineer")
            label = (engineer.display_name if engineer is not None and engineer.display_name else None) or (
                f"Engineer {run.engineer_id}"
            )
            return str(run.engineer_id), label
        if group_by == "week":
            if run.created_at is None:
                return "unknown", "Unknown"
            iso_year, iso_week, _ = run.created_at.isocalendar()
            key = f"{iso_year}-W{iso_week:02d}"
            return key, key
        raise ValueError(f"Unsupported group_by: {group_by}")

    async def _get_criticality_dimensions(self, tenant_id: int, cutoff: datetime) -> list[dict[str, Any]]:
        stmt = (
            select(
                AuditQuestion.criticality,
                AuditResponse.run_id,
                AuditResponse.question_id,
                AuditRun.status,
            )
            .join(AuditRun, AuditRun.id == AuditResponse.run_id)
            .join(AuditQuestion, AuditQuestion.id == AuditResponse.question_id)
            .where(AuditRun.tenant_id == tenant_id, AuditRun.created_at >= cutoff)
        )
        rows = (await self.db.execute(stmt)).all()
        if not rows:
            return []

        run_ids = {row.run_id for row in rows}
        finding_stmt = select(AuditFinding.run_id, AuditFinding.question_id).where(AuditFinding.run_id.in_(run_ids))
        finding_pairs = {(r, q) for r, q in (await self.db.execute(finding_stmt)).all()}

        buckets: dict[str, dict[str, Any]] = {}
        for criticality, run_id, question_id, status in rows:
            crit_value = _enum_value(criticality) or "unspecified"
            bucket = buckets.setdefault(
                crit_value,
                {"runs": set(), "completed_runs": set(), "total": 0, "failed": 0},
            )
            bucket["runs"].add(run_id)
            if _enum_value(status) == AuditStatus.COMPLETED.value:
                bucket["completed_runs"].add(run_id)
            bucket["total"] += 1
            if (run_id, question_id) in finding_pairs:
                bucket["failed"] += 1

        results = []
        for crit_value, bucket in buckets.items():
            fail_rate = (bucket["failed"] / bucket["total"] * 100) if bucket["total"] else 0.0
            results.append(
                {
                    "key": crit_value,
                    "label": crit_value.replace("_", " ").title(),
                    "run_count": len(bucket["runs"]),
                    "completed_count": len(bucket["completed_runs"]),
                    "avg_score": 0.0,
                    "fail_rate": round(fail_rate, 2),
                    "essential_compliance_pct": (
                        round(100 - fail_rate, 2) if crit_value == QuestionCriticality.ESSENTIAL.value else None
                    ),
                }
            )
        results.sort(key=lambda item: item["run_count"], reverse=True)
        return results

    async def get_dimensions(
        self,
        tenant_id: int,
        *,
        group_by: str,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        if group_by not in SUPPORTED_GROUP_BY:
            raise ValueError(f"Unsupported group_by: {group_by}")

        cutoff = _cutoff(days)

        if group_by == "criticality":
            return await self._get_criticality_dimensions(tenant_id, cutoff)

        stmt = (
            select(AuditRun)
            .options(
                selectinload(AuditRun.template),
                selectinload(AuditRun.asset_type),
                selectinload(AuditRun.run_location),
                selectinload(AuditRun.engineer),
            )
            .where(AuditRun.tenant_id == tenant_id, AuditRun.created_at >= cutoff)
        )
        runs = list((await self.db.execute(stmt)).scalars().all())
        if not runs:
            return []

        run_ids = [run.id for run in runs]
        essential_by_run = await self._essential_compliance_by_run(run_ids)

        buckets: dict[str, dict[str, Any]] = {}
        for run in runs:
            key, label = self._dimension_key_label(run, group_by)
            bucket = buckets.setdefault(
                key,
                {
                    "key": key,
                    "label": label,
                    "run_count": 0,
                    "completed_count": 0,
                    "_scores": [],
                    "_failed_runs": 0,
                    "_ess_total": 0,
                    "_ess_failed": 0,
                },
            )
            bucket["run_count"] += 1
            is_completed = _enum_value(run.status) == AuditStatus.COMPLETED.value
            if is_completed:
                bucket["completed_count"] += 1
                if run.score_percentage is not None:
                    bucket["_scores"].append(run.score_percentage)
            if run.passed is False:
                bucket["_failed_runs"] += 1
            ess_total, ess_failed = essential_by_run.get(run.id, (0, 0))
            bucket["_ess_total"] += ess_total
            bucket["_ess_failed"] += ess_failed

        results = []
        for bucket in buckets.values():
            avg_score = sum(bucket["_scores"]) / len(bucket["_scores"]) if bucket["_scores"] else 0.0
            fail_rate = (
                (bucket["_failed_runs"] / bucket["completed_count"] * 100) if bucket["completed_count"] else 0.0
            )
            essential_compliance_pct = (
                (1 - (bucket["_ess_failed"] / bucket["_ess_total"])) * 100 if bucket["_ess_total"] else 100.0
            )
            results.append(
                {
                    "key": bucket["key"],
                    "label": bucket["label"],
                    "run_count": bucket["run_count"],
                    "completed_count": bucket["completed_count"],
                    "avg_score": round(avg_score, 2),
                    "fail_rate": round(fail_rate, 2),
                    "essential_compliance_pct": round(essential_compliance_pct, 2),
                }
            )
        results.sort(key=lambda item: item["run_count"], reverse=True)
        return results

    async def _essential_compliance_by_run(self, run_ids: list[int]) -> dict[int, tuple[int, int]]:
        """Return {run_id: (total_essential_responses, failed_count)} for *run_ids*."""
        if not run_ids:
            return {}
        stmt = (
            select(AuditResponse.run_id, AuditResponse.question_id)
            .join(AuditQuestion, AuditQuestion.id == AuditResponse.question_id)
            .where(
                AuditResponse.run_id.in_(run_ids),
                AuditQuestion.criticality == QuestionCriticality.ESSENTIAL.value,
                (AuditResponse.applicability.is_(None))
                | (AuditResponse.applicability == ResponseApplicability.APPLICABLE.value),
            )
        )
        rows = (await self.db.execute(stmt)).all()
        if not rows:
            return {}
        finding_stmt = select(AuditFinding.run_id, AuditFinding.question_id).where(AuditFinding.run_id.in_(run_ids))
        finding_pairs = {(r, q) for r, q in (await self.db.execute(finding_stmt)).all()}

        stats: dict[int, list[int]] = {}
        for run_id, question_id in rows:
            total_failed = stats.setdefault(run_id, [0, 0])
            total_failed[0] += 1
            if (run_id, question_id) in finding_pairs:
                total_failed[1] += 1
        return {run_id: (total, failed) for run_id, (total, failed) in stats.items()}

    # ------------------------------------------------------------------
    # Critical queue (incomplete essential items)
    # ------------------------------------------------------------------

    async def get_critical_queue(
        self,
        tenant_id: int,
        *,
        limit: int = 200,
    ) -> list[CriticalQueueItem]:
        """Applicable essential items that are unanswered, or answered-and-failed
        with a still-open linked finding, across the tenant's active runs.
        """
        active_statuses = (
            AuditStatus.SCHEDULED.value,
            AuditStatus.IN_PROGRESS.value,
            AuditStatus.PENDING_REVIEW.value,
        )
        runs_stmt = (
            select(AuditRun)
            .options(selectinload(AuditRun.responses), selectinload(AuditRun.findings), selectinload(AuditRun.template))
            .where(AuditRun.tenant_id == tenant_id, AuditRun.status.in_(active_statuses))
        )
        runs = list((await self.db.execute(runs_stmt)).scalars().all())
        if not runs:
            return []

        template_ids = {run.template_id for run in runs}
        questions_stmt = select(AuditQuestion).where(
            AuditQuestion.template_id.in_(template_ids),
            AuditQuestion.criticality == QuestionCriticality.ESSENTIAL.value,
            AuditQuestion.is_active == True,  # noqa: E712
        )
        questions = list((await self.db.execute(questions_stmt)).scalars().all())
        if not questions:
            return []
        questions_by_template: dict[int, list[AuditQuestion]] = {}
        for question in questions:
            questions_by_template.setdefault(question.template_id, []).append(question)

        from src.domain.services.audit_composition import section_is_applicable

        section_ids = {q.section_id for q in questions if q.section_id is not None}
        sections_by_id: dict[int, Any] = {}
        if section_ids:
            from src.domain.models.audit import AuditSection

            sections_stmt = select(AuditSection).where(AuditSection.id.in_(section_ids))
            sections_by_id = {s.id: s for s in (await self.db.execute(sections_stmt)).scalars().all()}

        items: list[CriticalQueueItem] = []
        for run in runs:
            run_questions = questions_by_template.get(run.template_id, [])
            if not run_questions:
                continue
            responses_by_question = {r.question_id: r for r in (run.responses or [])}
            findings_by_question = {f.question_id: f for f in (run.findings or []) if f.question_id is not None}

            for question in run_questions:
                if question.section_id is not None:
                    section = sections_by_id.get(question.section_id)
                    if section is not None and not section_is_applicable(
                        section,
                        assessment_mode=run.assessment_mode,
                        asset_type_id=run.asset_type_id,
                    ):
                        continue

                response = responses_by_question.get(question.id)
                if response is not None and response.applicability == ResponseApplicability.HIDDEN_BY_LOGIC.value:
                    continue

                template_name = run.template.name if run.template else None

                if response is None or not AuditScoringService.response_is_answered(response):
                    items.append(
                        CriticalQueueItem(
                            run_id=run.id,
                            run_reference_number=run.reference_number,
                            template_id=run.template_id,
                            template_name=template_name,
                            question_id=question.id,
                            question_text=question.question_text,
                            reason="unanswered",
                        )
                    )
                    continue

                finding = findings_by_question.get(question.id)
                if finding is not None and _enum_value(finding.status) not in (
                    FindingStatus.CLOSED.value,
                    FindingStatus.DEFERRED.value,
                ):
                    items.append(
                        CriticalQueueItem(
                            run_id=run.id,
                            run_reference_number=run.reference_number,
                            template_id=run.template_id,
                            template_name=template_name,
                            question_id=question.id,
                            question_text=question.question_text,
                            reason="failed_open_finding",
                            finding_id=finding.id,
                            finding_status=_enum_value(finding.status),
                        )
                    )

        return items[:limit]

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    async def export_runs_csv(
        self,
        tenant_id: int,
        *,
        days: int = 90,
    ) -> str:
        """Run×response grain CSV including dimensions, applicability, criticality."""
        cutoff = _cutoff(days)
        stmt = (
            select(
                AuditRun.id.label("run_id"),
                AuditRun.reference_number,
                AuditRun.status,
                AuditRun.template_id,
                AuditTemplate.name.label("template_name"),
                AuditRun.assessment_mode,
                AuditRun.asset_type_id,
                AssetType.name.label("asset_type_name"),
                AuditRun.location_id,
                Location.name.label("location_name"),
                AuditRun.customer_code,
                AuditRun.engineer_id,
                Engineer.display_name.label("engineer_name"),
                AuditRun.score_percentage,
                AuditRun.passed,
                AuditRun.created_at,
                AuditResponse.question_id,
                AuditQuestion.question_text,
                AuditQuestion.criticality,
                AuditResponse.applicability,
                AuditResponse.is_na,
                AuditResponse.score,
                AuditResponse.max_score,
            )
            .join(AuditResponse, AuditResponse.run_id == AuditRun.id)
            .join(AuditQuestion, AuditQuestion.id == AuditResponse.question_id)
            .outerjoin(AuditTemplate, AuditTemplate.id == AuditRun.template_id)
            .outerjoin(AssetType, AssetType.id == AuditRun.asset_type_id)
            .outerjoin(Location, Location.id == AuditRun.location_id)
            .outerjoin(Engineer, Engineer.id == AuditRun.engineer_id)
            .where(AuditRun.tenant_id == tenant_id, AuditRun.created_at >= cutoff)
            .order_by(AuditRun.id, AuditResponse.question_id)
        )
        rows = (await self.db.execute(stmt)).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "run_id",
                "reference_number",
                "status",
                "template_id",
                "template_name",
                "assessment_mode",
                "asset_type_id",
                "asset_type_name",
                "location_id",
                "location_name",
                "customer_code",
                "engineer_id",
                "engineer_name",
                "score_percentage",
                "passed",
                "created_at",
                "question_id",
                "question_text",
                "criticality",
                "applicability",
                "is_na",
                "score",
                "max_score",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.run_id,
                    row.reference_number,
                    _enum_value(row.status),
                    row.template_id,
                    row.template_name,
                    row.assessment_mode,
                    row.asset_type_id,
                    row.asset_type_name,
                    row.location_id,
                    row.location_name,
                    row.customer_code,
                    row.engineer_id,
                    row.engineer_name,
                    row.score_percentage,
                    row.passed,
                    row.created_at.isoformat() if row.created_at else "",
                    row.question_id,
                    row.question_text,
                    _enum_value(row.criticality),
                    row.applicability or ResponseApplicability.APPLICABLE.value,
                    row.is_na,
                    row.score,
                    row.max_score,
                ]
            )
        return buffer.getvalue()
