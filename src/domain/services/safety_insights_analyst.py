"""Safety Insights Analyst — corpus, dimensions, micro-themes, ratios, synthesis."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, time, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision
from src.domain.models.safety_insight import (
    SafetyInsightDimension,
    SafetyInsightRun,
    SafetyInsightRunStatus,
    SafetyInsightTheme,
    SafetyInsightThemeCase,
)
from src.domain.services.gemini_ai_service import GeminiAIService
from src.domain.services.hs_kpi_service import HsKpiService

logger = logging.getLogger(__name__)

ALL_MODULES = ("incident", "near_miss", "rta", "complaint")
MODULE_ALIASES = {
    "incidents": "incident",
    "incident": "incident",
    "near_misses": "near_miss",
    "near_miss": "near_miss",
    "nearmiss": "near_miss",
    "rtas": "rta",
    "rta": "rta",
    "complaints": "complaint",
    "complaint": "complaint",
}


class SafetyInsightsAnalystService:
    """Orchestrates a deep-run over H&S case corpora."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.gemini = GeminiAIService()

    # ------------------------------------------------------------------ create / queue
    async def create_run(
        self,
        *,
        tenant_id: int,
        user_id: Optional[int],
        modules: list[str],
        scope: str = "org",
        topic_query: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_cluster_size: int = 2,
        include_synthesis: bool = True,
        include_benchmark: bool = False,
    ) -> SafetyInsightRun:
        normalised = self._normalise_modules(modules)
        if not normalised:
            raise ValueError("At least one module is required")
        if scope not in {"org", "topic"}:
            raise ValueError("scope must be org or topic")
        if scope == "topic" and not (topic_query or "").strip():
            raise ValueError("topic_query is required when scope=topic")
        run = SafetyInsightRun(
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
            status=SafetyInsightRunStatus.QUEUED,
            progress_pct=0,
            progress_message="Queued",
            scope=scope,
            topic_query=(topic_query or "").strip() or None,
            modules_json=normalised,
            date_from=date_from,
            date_to=date_to,
            min_cluster_size=max(2, int(min_cluster_size or 2)),
            include_synthesis=bool(include_synthesis),
            include_benchmark=bool(include_benchmark),
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def process_run(self, run_id: int, tenant_id: int) -> SafetyInsightRun:
        run = await self._get_run(run_id, tenant_id)
        if run is None:
            raise ValueError("Run not found")
        if run.status == SafetyInsightRunStatus.SUCCEEDED:
            return run
        if run.status == SafetyInsightRunStatus.RUNNING:
            # Another worker already claimed this run; avoid interleaved theme writes.
            return run

        run.status = SafetyInsightRunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)
        run.progress_pct = 5
        run.progress_message = "Building corpus"
        run.error_code = None
        run.error_detail = None
        # Commit progress so pollers see RUNNING (flush alone stays invisible).
        await self.db.commit()

        models_used: dict[str, Any] = {"clustering": None, "synthesis": None, "research": None}

        try:
            if not self.gemini.is_configured():
                raise RuntimeError("GEMINI_UNAVAILABLE")

            corpus = await self.build_corpus(
                tenant_id=tenant_id,
                modules=list(run.modules_json or []),
                date_from=run.date_from,
                date_to=run.date_to,
                topic_query=run.topic_query if run.scope == "topic" else None,
            )
            run.corpus_summary_json = {
                "total_cases": len(corpus),
                "by_module": self._count_by_module(corpus),
                "scope": run.scope,
                "topic_query": run.topic_query,
            }
            run.quality_scorecard_json = self.compute_quality_scorecard(corpus)
            run.progress_pct = 25
            run.progress_message = "Rolling up dimensions"
            await self.db.commit()

            dimensions = self.dimension_rollups(corpus)
            await self._replace_dimensions(run, dimensions)

            run.progress_pct = 40
            run.progress_message = "Clustering micro-themes"
            await self.db.commit()

            raw_themes = await self.cluster_micro_themes(corpus, min_cluster_size=run.min_cluster_size)
            models_used["clustering"] = os.environ.get("GEMINI_MODEL", "gemini-3.1-pro-preview")
            validated = self.validate_citations(raw_themes, corpus, min_cluster_size=run.min_cluster_size)
            validated = self.annotate_theme_velocity(validated, corpus)
            await self._replace_themes(run, validated)

            run.progress_pct = 65
            run.progress_message = "Computing internal benchmarks"
            await self.db.commit()
            run.ratios_json = await self.compute_internal_benchmarks(
                tenant_id=tenant_id,
                date_from=run.date_from,
                date_to=run.date_to,
                corpus=corpus,
            )

            synthesis_text = None
            synthesis_available = False
            if run.include_synthesis:
                run.progress_pct = 80
                run.progress_message = "Synthesising analyst note"
                await self.db.commit()
                synthesis_text, synthesis_available, synth_model = await self.synthesize_analyst_note(
                    corpus_summary=run.corpus_summary_json,
                    themes=validated,
                    dimensions=dimensions[:12],
                    ratios=run.ratios_json,
                    quality=run.quality_scorecard_json,
                )
                models_used["synthesis"] = synth_model
            run.synthesis_text = synthesis_text
            run.synthesis_available = synthesis_available

            benchmarks: list[dict[str, Any]] = []
            research_available = False
            if run.include_benchmark:
                run.progress_pct = 90
                run.progress_message = "External HSE research"
                await self.db.commit()
                benchmarks, research_available = await asyncio.to_thread(
                    self.benchmark_external, validated, run.ratios_json or {}
                )
                models_used["research"] = "perplexity-sonar" if research_available else None
            run.benchmarks_json = benchmarks
            run.research_available = research_available

            # Additive training/competence correlation (fail-soft; never invent).
            try:
                from src.domain.services.safety_insights_training import correlate_training_signals

                training_signals = await correlate_training_signals(
                    self.db,
                    tenant_id=tenant_id,
                    theme_labels=[t.get("label") or "" for t in validated],
                    modules=list(run.modules_json or []),
                )
            except Exception as exc:  # noqa: BLE001
                logger.info("Training correlation unavailable: %s", type(exc).__name__)
                from src.domain.services.safety_insights_training import empty_training_signals

                training_signals = empty_training_signals(reason=f"correlation_failed:{type(exc).__name__}")
            ratios = dict(run.ratios_json or {})
            ratios["training_signals"] = training_signals
            run.ratios_json = ratios
            models_used["training"] = "competence_gap+training_tickets"
            run.models_used_json = models_used

            run.status = SafetyInsightRunStatus.SUCCEEDED
            run.progress_pct = 100
            run.progress_message = "Complete"
            run.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            return run
        except Exception as exc:  # noqa: BLE001
            code = "GEMINI_UNAVAILABLE" if "GEMINI_UNAVAILABLE" in str(exc) else type(exc).__name__
            logger.exception("Safety insights run %s failed", run_id)
            run.status = SafetyInsightRunStatus.FAILED
            run.error_code = code[:100]
            run.error_detail = str(exc)[:2000]
            run.progress_message = "Failed"
            run.completed_at = datetime.now(timezone.utc)
            run.models_used_json = models_used
            # Persist FAILED even if the outer Celery/API wrapper would otherwise roll back.
            await self.db.commit()
            raise

    # ------------------------------------------------------------------ corpus
    async def build_corpus(  # noqa: C901 - four module loaders with shared filters
        self,
        *,
        tenant_id: int,
        modules: list[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        topic_query: Optional[str],
        limit_per_module: int = 250,
    ) -> list[dict[str, Any]]:
        modules = self._normalise_modules(modules)
        topic = (topic_query or "").strip().lower() or None
        rows: list[dict[str, Any]] = []

        if "incident" in modules:
            q_incident = select(Incident).where(Incident.tenant_id == tenant_id)
            if date_from is not None:
                q_incident = q_incident.where(Incident.incident_date >= date_from)
            if date_to is not None:
                q_incident = q_incident.where(Incident.incident_date <= date_to)
            q_incident = q_incident.order_by(Incident.incident_date.desc()).limit(limit_per_module)
            for incident_row in (await self.db.execute(q_incident)).scalars().all():
                item = {
                    "module": "incident",
                    "id": incident_row.id,
                    "reference_number": incident_row.reference_number,
                    "event_date": incident_row.incident_date,
                    "title": getattr(incident_row, "title", None) or "",
                    "description": incident_row.description or "",
                    "location": incident_row.location or "",
                    "department": incident_row.department or "",
                    "contract": "",
                    "person": incident_row.reporter_name or incident_row.reporter_email or "",
                    "people": incident_row.people_involved or "",
                    "vehicle": "",
                    "asset_id": incident_row.asset_id,
                    "root_cause": incident_row.root_cause or "",
                    "severity": str(getattr(incident_row, "severity", "") or ""),
                    "is_hipo": False,
                }
                if topic and not self._matches_topic(item, topic):
                    continue
                rows.append(item)

        if "near_miss" in modules:
            q_near_miss = select(NearMiss).where(NearMiss.tenant_id == tenant_id)
            if date_from is not None:
                q_near_miss = q_near_miss.where(NearMiss.event_date >= date_from)
            if date_to is not None:
                q_near_miss = q_near_miss.where(NearMiss.event_date <= date_to)
            q_near_miss = q_near_miss.order_by(NearMiss.event_date.desc()).limit(limit_per_module)
            for near_miss_row in (await self.db.execute(q_near_miss)).scalars().all():
                item = {
                    "module": "near_miss",
                    "id": near_miss_row.id,
                    "reference_number": near_miss_row.reference_number,
                    "event_date": near_miss_row.event_date,
                    "title": "",
                    "description": near_miss_row.description or "",
                    "location": near_miss_row.location or "",
                    "department": "",
                    "contract": near_miss_row.contract or "",
                    "person": near_miss_row.reporter_name or near_miss_row.reporter_email or "",
                    "people": near_miss_row.persons_involved or "",
                    "vehicle": "",
                    "asset_id": near_miss_row.asset_id,
                    "root_cause": "",
                    "severity": near_miss_row.potential_severity or "",
                    "is_hipo": bool(near_miss_row.is_hipo),
                }
                if topic and not self._matches_topic(item, topic):
                    continue
                rows.append(item)

        if "rta" in modules:
            q_rta = select(RoadTrafficCollision).where(RoadTrafficCollision.tenant_id == tenant_id)
            if date_from is not None:
                q_rta = q_rta.where(RoadTrafficCollision.collision_date >= date_from)
            if date_to is not None:
                q_rta = q_rta.where(RoadTrafficCollision.collision_date <= date_to)
            q_rta = q_rta.order_by(RoadTrafficCollision.collision_date.desc()).limit(limit_per_module)
            for rta_row in (await self.db.execute(q_rta)).scalars().all():
                item = {
                    "module": "rta",
                    "id": rta_row.id,
                    "reference_number": rta_row.reference_number,
                    "event_date": rta_row.collision_date,
                    "title": rta_row.collision_type or "",
                    "description": rta_row.description or "",
                    "location": rta_row.location or "",
                    "department": "",
                    "contract": "",
                    "person": rta_row.driver_name or rta_row.driver_email or "",
                    "people": "",
                    "vehicle": (rta_row.company_vehicle_registration or "").upper(),
                    "asset_id": rta_row.asset_id,
                    "root_cause": rta_row.root_cause or "",
                    "severity": "",
                    "is_hipo": False,
                }
                if topic and not self._matches_topic(item, topic):
                    continue
                rows.append(item)

        if "complaint" in modules:
            q_complaint = select(Complaint).where(Complaint.tenant_id == tenant_id)
            date_field = getattr(Complaint, "received_date", None) or Complaint.created_at
            if date_from is not None:
                q_complaint = q_complaint.where(date_field >= date_from)
            if date_to is not None:
                q_complaint = q_complaint.where(date_field <= date_to)
            q_complaint = q_complaint.order_by(date_field.desc()).limit(limit_per_module)
            for complaint_row in (await self.db.execute(q_complaint)).scalars().all():
                item = {
                    "module": "complaint",
                    "id": complaint_row.id,
                    "reference_number": complaint_row.reference_number,
                    "event_date": getattr(complaint_row, "received_date", None) or complaint_row.created_at,
                    "title": getattr(complaint_row, "title", None) or "",
                    "description": complaint_row.description or "",
                    "location": getattr(complaint_row, "location", None) or "",
                    "department": getattr(complaint_row, "department", None) or "",
                    "contract": str(getattr(complaint_row, "contract_id", "") or ""),
                    "person": getattr(complaint_row, "complainant_name", None)
                    or getattr(complaint_row, "subject_name", None)
                    or "",
                    "people": "",
                    "vehicle": "",
                    "asset_id": None,
                    "root_cause": getattr(complaint_row, "root_cause", None) or "",
                    "severity": str(getattr(complaint_row, "severity", "") or ""),
                    "is_hipo": False,
                }
                if topic and not self._matches_topic(item, topic):
                    continue
                rows.append(item)

        return rows

    # ------------------------------------------------------------------ dimensions / quality
    def dimension_rollups(self, corpus: list[dict[str, Any]], *, top_n: int = 25) -> list[dict[str, Any]]:
        buckets: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

        def _add(dim: str, key: str, case: dict[str, Any]) -> None:
            key = (key or "").strip()
            if not key or key.lower() in {"unknown", "n/a", "none", "-"}:
                return
            buckets[(dim, key[:300])].append(
                {
                    "module": case["module"],
                    "id": case["id"],
                    "reference_number": case["reference_number"],
                }
            )

        for case in corpus:
            _add("location", case.get("location") or "", case)
            _add("contract", case.get("contract") or case.get("department") or "", case)
            _add("person", case.get("person") or "", case)
            for person in re.split(r"[,;|/]", case.get("people") or ""):
                _add("person", person, case)
            _add("vehicle", case.get("vehicle") or "", case)
            if case.get("asset_id"):
                _add("asset", f"asset:{case['asset_id']}", case)

        ranked: list[dict[str, Any]] = []
        for (dim, key), refs in buckets.items():
            # unique by module+id
            seen = set()
            unique_refs = []
            for ref in refs:
                token = (ref["module"], ref["id"])
                if token in seen:
                    continue
                seen.add(token)
                unique_refs.append(ref)
            if len(unique_refs) < 2:
                continue
            ranked.append(
                {
                    "dimension_type": dim,
                    "dimension_key": key,
                    "case_count": len(unique_refs),
                    "case_refs": unique_refs,
                }
            )
        ranked.sort(key=lambda r: (-r["case_count"], r["dimension_type"], r["dimension_key"]))
        for idx, row in enumerate(ranked[:top_n]):
            row["sort_order"] = idx
        return ranked[:top_n]

    def compute_quality_scorecard(self, corpus: list[dict[str, Any]]) -> dict[str, Any]:
        if not corpus:
            return {"total": 0, "fields": {}}

        def _pct(predicate) -> float:
            hit = sum(1 for c in corpus if predicate(c))
            return round(100.0 * hit / len(corpus), 1)

        return {
            "total": len(corpus),
            "fields": {
                "missing_root_cause_pct": _pct(
                    lambda c: c["module"] != "near_miss" and not (c.get("root_cause") or "").strip()
                ),
                "missing_location_pct": _pct(lambda c: not (c.get("location") or "").strip()),
                "missing_person_pct": _pct(lambda c: not (c.get("person") or "").strip()),
                "rta_missing_vehicle_pct": (
                    round(
                        100.0
                        * sum(1 for c in corpus if c["module"] == "rta" and not (c.get("vehicle") or "").strip())
                        / max(1, sum(1 for c in corpus if c["module"] == "rta")),
                        1,
                    )
                    if any(c["module"] == "rta" for c in corpus)
                    else None
                ),
            },
        }

    # ------------------------------------------------------------------ AI themes
    async def cluster_micro_themes(
        self, corpus: list[dict[str, Any]], *, min_cluster_size: int = 2
    ) -> list[dict[str, Any]]:
        if len(corpus) < min_cluster_size:
            return []

        # Chunk to keep prompts bounded
        chunk_size = 80
        merged: list[dict[str, Any]] = []
        for start in range(0, len(corpus), chunk_size):
            chunk = corpus[start : start + chunk_size]
            payload = [
                {
                    "module": c["module"],
                    "id": c["id"],
                    "ref": c["reference_number"],
                    "text": " | ".join(
                        x
                        for x in [
                            c.get("title") or "",
                            (c.get("description") or "")[:400],
                            c.get("root_cause") or "",
                            c.get("collision_type") if False else "",
                            c.get("location") or "",
                        ]
                        if x
                    )[:700],
                }
                for c in chunk
            ]
            prompt = f"""You are a health & safety research analyst.
Cluster the following workplace cases into micro-themes (specific narrative patterns, not broad categories).
Only assign a case to a theme when the narrative clearly matches. Prefer themes with at least {min_cluster_size} cases.
Return ONLY valid JSON:
{{
  "themes": [
    {{
      "label": "short specific theme e.g. reversing into stationary object",
      "rationale": "one sentence",
      "module_scope": "rta|incident|near_miss|complaint|mixed",
      "severity_overlay": "low|medium|high|critical|mixed",
      "case_refs": [{{"module":"rta","id":12,"reference_number":"RTA-2026-0012"}}]
    }}
  ]
}}

Cases:
{json.dumps(payload, default=str)}
"""
            raw = await self.gemini.generate_json(prompt)
            themes = raw.get("themes") if isinstance(raw, dict) else raw
            if isinstance(themes, list):
                merged.extend(t for t in themes if isinstance(t, dict))

        # Merge same labels across chunks
        by_label: dict[str, dict[str, Any]] = {}
        for theme in merged:
            label = str(theme.get("label") or "").strip()
            if not label:
                continue
            key = label.lower()
            bucket = by_label.setdefault(
                key,
                {
                    "label": label,
                    "rationale": theme.get("rationale") or "",
                    "module_scope": theme.get("module_scope") or "mixed",
                    "severity_overlay": theme.get("severity_overlay") or "mixed",
                    "case_refs": [],
                },
            )
            for ref in theme.get("case_refs") or []:
                if isinstance(ref, dict):
                    bucket["case_refs"].append(ref)
        return list(by_label.values())

    def validate_citations(
        self,
        themes: list[dict[str, Any]],
        corpus: list[dict[str, Any]],
        *,
        min_cluster_size: int = 2,
    ) -> list[dict[str, Any]]:
        index = {(c["module"], int(c["id"])): c for c in corpus}
        by_ref = {str(c["reference_number"]).upper(): c for c in corpus if c.get("reference_number")}
        validated: list[dict[str, Any]] = []
        for theme in themes:
            seen = set()
            refs: list[dict[str, Any]] = []
            for raw in theme.get("case_refs") or []:
                if not isinstance(raw, dict):
                    continue
                module = MODULE_ALIASES.get(str(raw.get("module") or "").lower())
                case_id = raw.get("id")
                ref_no = str(raw.get("reference_number") or raw.get("ref") or "").upper()
                case = None
                if module and case_id is not None:
                    try:
                        case = index.get((module, int(case_id)))
                    except (TypeError, ValueError):
                        case = None
                if case is None and ref_no:
                    case = by_ref.get(ref_no)
                if case is None:
                    continue
                token = (case["module"], case["id"])
                if token in seen:
                    continue
                seen.add(token)
                refs.append(
                    {
                        "module": case["module"],
                        "id": case["id"],
                        "reference_number": case["reference_number"],
                    }
                )
            if len(refs) < min_cluster_size:
                continue
            total = max(1, len(corpus))
            validated.append(
                {
                    "label": str(theme.get("label") or "").strip()[:300],
                    "rationale": str(theme.get("rationale") or "")[:1000],
                    "module_scope": str(theme.get("module_scope") or "mixed")[:50],
                    "severity_overlay": str(theme.get("severity_overlay") or "mixed")[:50],
                    "case_count": len(refs),
                    "share": round(100.0 * len(refs) / total, 1),
                    "case_refs": refs,
                    "velocity": "stable",
                }
            )
        validated.sort(key=lambda t: (-t["case_count"], t["label"].lower()))
        for idx, theme in enumerate(validated):
            theme["sort_order"] = idx
        return validated

    def annotate_theme_velocity(
        self, themes: list[dict[str, Any]], corpus: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        dated = [c for c in corpus if c.get("event_date")]
        if len(dated) < 4:
            return themes
        dates = sorted(c["event_date"] for c in dated)
        mid = dates[len(dates) // 2]
        early_ids = {(c["module"], c["id"]) for c in dated if c["event_date"] <= mid}
        late_ids = {(c["module"], c["id"]) for c in dated if c["event_date"] > mid}
        for theme in themes:
            refs = {(r["module"], r["id"]) for r in theme.get("case_refs") or []}
            early = len(refs & early_ids)
            late = len(refs & late_ids)
            if late >= early + 2:
                theme["velocity"] = "emerging"
            elif early >= late + 2:
                theme["velocity"] = "declining"
            else:
                theme["velocity"] = "stable"
        return themes

    # ------------------------------------------------------------------ ratios / synthesis / research
    async def compute_internal_benchmarks(
        self,
        *,
        tenant_id: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        corpus: list[dict[str, Any]],
    ) -> dict[str, Any]:
        incidents = sum(1 for c in corpus if c["module"] == "incident")
        near_misses = sum(1 for c in corpus if c["module"] == "near_miss")
        hipo = sum(1 for c in corpus if c["module"] == "near_miss" and c.get("is_hipo"))
        nm_ratio = round(near_misses / incidents, 2) if incidents else None
        hipo_ratio = round(hipo / incidents, 2) if incidents else None

        # Period board ratios from HsKpiService for latest year overlap
        board: list[dict[str, Any]] = []
        try:
            kpi = HsKpiService(self.db)
            summary = await kpi.summary(tenant_id)
            for period in summary.get("by_year") or []:
                inj = int(period.get("injuries") or 0)
                # Prefer incident-like denominator: injuries for board; also expose NM vs injuries
                nm = int(period.get("near_misses") or 0)
                hipo_nm = int(period.get("hipo_near_misses") or 0)
                board.append(
                    {
                        "reporting_year": period.get("reporting_year"),
                        "near_miss_to_injury_ratio": round(nm / inj, 2) if inj else None,
                        "hipo_near_miss_to_injury_ratio": round(hipo_nm / inj, 2) if inj else None,
                        "near_misses": nm,
                        "injuries": inj,
                        "hipo_near_misses": hipo_nm,
                        "ltifr": period.get("ltifr"),
                        "afr": period.get("afr"),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            logger.info("HS KPI board ratios unavailable: %s", type(exc).__name__)

        return {
            "corpus": {
                "incidents": incidents,
                "near_misses": near_misses,
                "hipo_near_misses": hipo,
                "near_miss_to_incident_ratio": nm_ratio,
                "hipo_near_miss_to_incident_ratio": hipo_ratio,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            },
            "hs_board_by_year": board,
        }

    async def synthesize_analyst_note(
        self,
        *,
        corpus_summary: dict[str, Any],
        themes: list[dict[str, Any]],
        dimensions: list[dict[str, Any]],
        ratios: dict[str, Any],
        quality: dict[str, Any],
    ) -> tuple[Optional[str], bool, Optional[str]]:
        api_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        if not api_key:
            return None, False, None
        try:
            from src.domain.services.ai_models import AIConfig, AnthropicClient

            client = AnthropicClient(AIConfig.from_env())
            theme_lines = [
                f"- {t['label']} (n={t['case_count']}, {t.get('velocity')}: "
                f"{', '.join(r['reference_number'] for r in (t.get('case_refs') or [])[:8])})"
                for t in themes[:15]
            ]
            dim_lines = [
                f"- {d['dimension_type']}: {d['dimension_key']} (n={d['case_count']})" for d in dimensions[:10]
            ]
            prompt = f"""Write a concise H&S research-analyst note (5-8 short paragraphs).
Rules:
- Only refer to themes/cases listed below; never invent case references.
- Call out near-miss:incident ratios and emerging vs declining themes.
- Note capture-quality limitations if material.
- End with 3 recommended focus areas for leadership.

Corpus: {json.dumps(corpus_summary)}
Ratios: {json.dumps(ratios)}
Quality: {json.dumps(quality)}
Themes:
{chr(10).join(theme_lines) or '(none)'}
Repeat dimensions:
{chr(10).join(dim_lines) or '(none)'}
"""
            text = await client.complete(
                prompt,
                system_prompt=(
                    "You are a world-class health and safety research analyst. "
                    "Be precise, cite case refs already provided, do not invent data."
                ),
                temperature=0.3,
                max_tokens=2500,
            )
            model = getattr(client, "model", None) or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
            return (text or "").strip() or None, bool((text or "").strip()), model
        except Exception as exc:  # noqa: BLE001
            logger.info("Claude synthesis unavailable: %s", type(exc).__name__)
            return None, False, None

    def benchmark_external(
        self, themes: list[dict[str, Any]], ratios: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], bool]:
        try:
            from src.domain.services.library_horizon_adapter import research_with_perplexity
        except Exception:  # noqa: BLE001
            return [], False
        top = ", ".join(t["label"] for t in themes[:5]) or "workplace safety"
        nm = (ratios.get("corpus") or {}).get("near_miss_to_incident_ratio")
        query = (
            "UK HSE.gov.uk and gov.uk statistics for utilities/field operations: "
            f"benchmark near-miss to incident reporting culture (our corpus ratio={nm}), "
            f"and public guidance related to these micro-themes: {top}. "
            "Prefer HSE.gov.uk sources with URLs."
        )
        findings = research_with_perplexity(query) or []
        out: list[dict[str, Any]] = []
        for item in findings[:8]:
            out.append(
                {
                    "title": getattr(item, "title", None) or getattr(item, "headline", None) or "Finding",
                    "summary": getattr(item, "summary", None) or getattr(item, "detail", None) or str(item),
                    "source_url": getattr(item, "source_url", None) or getattr(item, "url", None),
                }
            )
        return out, bool(out)

    # ------------------------------------------------------------------ reads / serialize
    async def get_run(self, run_id: int, tenant_id: int) -> Optional[SafetyInsightRun]:
        return await self._get_run(run_id, tenant_id)

    async def list_runs(self, tenant_id: int, *, limit: int = 20) -> list[SafetyInsightRun]:
        result = await self.db.execute(
            select(SafetyInsightRun)
            .where(SafetyInsightRun.tenant_id == tenant_id)
            .order_by(SafetyInsightRun.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_runs(self, tenant_id: int) -> int:
        from sqlalchemy import func

        result = await self.db.execute(
            select(func.count()).select_from(SafetyInsightRun).where(SafetyInsightRun.tenant_id == tenant_id)
        )
        return int(result.scalar_one())

    async def latest_succeeded(self, tenant_id: int) -> Optional[SafetyInsightRun]:
        result = await self.db.execute(
            select(SafetyInsightRun)
            .where(
                SafetyInsightRun.tenant_id == tenant_id,
                SafetyInsightRun.status == SafetyInsightRunStatus.SUCCEEDED,
            )
            .order_by(SafetyInsightRun.completed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def serialize_run(self, run: SafetyInsightRun, *, include_children: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": run.id,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "progress_pct": run.progress_pct,
            "progress_message": run.progress_message,
            "scope": run.scope,
            "topic_query": run.topic_query,
            "modules": run.modules_json,
            "date_from": run.date_from.isoformat() if run.date_from else None,
            "date_to": run.date_to.isoformat() if run.date_to else None,
            "min_cluster_size": run.min_cluster_size,
            "include_synthesis": run.include_synthesis,
            "include_benchmark": run.include_benchmark,
            "corpus_summary": run.corpus_summary_json,
            "ratios": run.ratios_json,
            "quality_scorecard": run.quality_scorecard_json,
            "synthesis_text": run.synthesis_text,
            "benchmarks": run.benchmarks_json or [],
            "synthesis_available": run.synthesis_available,
            "research_available": run.research_available,
            "models_used": run.models_used_json,
            "error_code": run.error_code,
            "error_detail": run.error_detail,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        if include_children:
            themes = (
                (
                    await self.db.execute(
                        select(SafetyInsightTheme)
                        .where(SafetyInsightTheme.run_id == run.id)
                        .order_by(SafetyInsightTheme.sort_order)
                    )
                )
                .scalars()
                .all()
            )
            theme_cases = (
                (await self.db.execute(select(SafetyInsightThemeCase).where(SafetyInsightThemeCase.run_id == run.id)))
                .scalars()
                .all()
            )
            by_theme: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for tc in theme_cases:
                by_theme[tc.theme_id].append(
                    {"module": tc.module, "id": tc.case_id, "reference_number": tc.reference_number}
                )
            payload["micro_themes"] = [
                {
                    "id": t.id,
                    "label": t.label,
                    "rationale": t.rationale,
                    "module_scope": t.module_scope,
                    "case_count": t.case_count,
                    "share": t.share,
                    "velocity": t.velocity,
                    "severity_overlay": t.severity_overlay,
                    "case_refs": by_theme.get(t.id, []),
                }
                for t in themes
            ]
            dims = (
                (
                    await self.db.execute(
                        select(SafetyInsightDimension)
                        .where(SafetyInsightDimension.run_id == run.id)
                        .order_by(SafetyInsightDimension.sort_order)
                    )
                )
                .scalars()
                .all()
            )
            payload["dimensions"] = [
                {
                    "id": d.id,
                    "dimension_type": d.dimension_type,
                    "dimension_key": d.dimension_key,
                    "case_count": d.case_count,
                    "case_refs": d.case_refs_json or [],
                }
                for d in dims
            ]
        return payload

    async def theme_case_ids(self, theme_id: int, tenant_id: int) -> Optional[dict[str, Any]]:
        theme = (
            await self.db.execute(
                select(SafetyInsightTheme).where(
                    SafetyInsightTheme.id == theme_id, SafetyInsightTheme.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if theme is None:
            return None
        cases = (
            (
                await self.db.execute(
                    select(SafetyInsightThemeCase).where(
                        SafetyInsightThemeCase.theme_id == theme_id,
                        SafetyInsightThemeCase.tenant_id == tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        by_module: dict[str, list[int]] = defaultdict(list)
        refs = []
        for c in cases:
            by_module[c.module].append(c.case_id)
            refs.append({"module": c.module, "id": c.case_id, "reference_number": c.reference_number})
        return {"theme_id": theme_id, "label": theme.label, "by_module": dict(by_module), "case_refs": refs}

    # ------------------------------------------------------------------ internals
    async def _get_run(self, run_id: int, tenant_id: int) -> Optional[SafetyInsightRun]:
        return (
            await self.db.execute(
                select(SafetyInsightRun).where(SafetyInsightRun.id == run_id, SafetyInsightRun.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()

    async def _replace_dimensions(self, run: SafetyInsightRun, dimensions: list[dict[str, Any]]) -> None:
        existing = (
            (await self.db.execute(select(SafetyInsightDimension).where(SafetyInsightDimension.run_id == run.id)))
            .scalars()
            .all()
        )
        for row in existing:
            await self.db.delete(row)
        for dim in dimensions:
            self.db.add(
                SafetyInsightDimension(
                    run_id=run.id,
                    tenant_id=run.tenant_id,
                    dimension_type=dim["dimension_type"],
                    dimension_key=dim["dimension_key"],
                    case_count=dim["case_count"],
                    case_refs_json=dim["case_refs"],
                    sort_order=dim.get("sort_order", 0),
                )
            )
        await self.db.flush()

    async def _replace_themes(self, run: SafetyInsightRun, themes: list[dict[str, Any]]) -> None:
        old_themes = (
            (await self.db.execute(select(SafetyInsightTheme).where(SafetyInsightTheme.run_id == run.id)))
            .scalars()
            .all()
        )
        old_cases = (
            (await self.db.execute(select(SafetyInsightThemeCase).where(SafetyInsightThemeCase.run_id == run.id)))
            .scalars()
            .all()
        )
        for case_row in old_cases:
            await self.db.delete(case_row)
        for theme_row in old_themes:
            await self.db.delete(theme_row)
        await self.db.flush()
        for theme in themes:
            theme_row = SafetyInsightTheme(
                run_id=run.id,
                tenant_id=run.tenant_id,
                label=theme["label"],
                rationale=theme.get("rationale"),
                module_scope=theme.get("module_scope"),
                case_count=theme["case_count"],
                share=theme.get("share"),
                velocity=theme.get("velocity"),
                severity_overlay=theme.get("severity_overlay"),
                sort_order=theme.get("sort_order", 0),
            )
            self.db.add(theme_row)
            await self.db.flush()
            for ref in theme.get("case_refs") or []:
                self.db.add(
                    SafetyInsightThemeCase(
                        theme_id=theme_row.id,
                        run_id=run.id,
                        tenant_id=run.tenant_id,
                        module=ref["module"],
                        case_id=ref["id"],
                        reference_number=ref["reference_number"],
                    )
                )
        await self.db.flush()

    @staticmethod
    def _normalise_modules(modules: list[str]) -> list[str]:
        out: list[str] = []
        for m in modules or list(ALL_MODULES):
            key = MODULE_ALIASES.get(str(m).lower().strip())
            if key and key not in out:
                out.append(key)
        return out

    @staticmethod
    def _count_by_module(corpus: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for c in corpus:
            counts[c["module"]] += 1
        return dict(counts)

    @staticmethod
    def _matches_topic(item: dict[str, Any], topic: str) -> bool:
        blob = " ".join(
            str(item.get(k) or "")
            for k in ("title", "description", "root_cause", "location", "vehicle", "people", "person")
        ).lower()
        return topic in blob

    @staticmethod
    def parse_date_bound(value: Optional[str], *, end: bool = False) -> Optional[datetime]:
        if not value:
            return None
        raw = value.strip()
        if len(raw) == 10:
            d = datetime.fromisoformat(raw).date()
            t = time.max if end else time.min
            return datetime.combine(d, t, tzinfo=timezone.utc)
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
