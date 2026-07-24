"""AI Audit Builder orchestrator — brief, Q&A, similar templates, generate prompt.

Fail-closed: platform/context/research failures degrade to empty signals; generation
still proceeds from user intent + uploads.
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)

ALLOWED_PURPOSES = frozenset(
    {
        "risk_audit",
        "technical_assessment",
        "vehicle_asset_check",
        "iso_scheme",
        "case_follow_up",
        "freeform",
    }
)

ALLOWED_SCOPES = frozenset(
    {
        "incidents",
        "near_misses",
        "rtas",
        "complaints",
        "engineers",
        "documents",
    }
)

ALLOWED_STANDARDS = frozenset(
    {
        "ISO 9001",
        "ISO 27001",
        "ISO 45001",
        "ISO 14001",
        "UVDB-Achilles",
        "Planet Mark",
        "HSE",
    }
)


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]{3,}", (text or "").lower())}


def _overlap_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta, tb = _token_set(a), _token_set(b)
    if not ta or not tb:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    inter = len(ta & tb)
    union = len(ta | tb)
    jaccard = inter / union if union else 0.0
    seq = SequenceMatcher(None, a.lower()[:200], b.lower()[:200]).ratio()
    return 0.65 * jaccard + 0.35 * seq


class AuditBuilderOrchestrator:
    """Coordinates intent → context → brief → Q&A → similar gate → generate prompt."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def gather_brief(
        self,
        *,
        tenant_id: int,
        purpose: str,
        scopes: list[str],
        case_refs: list[dict[str, Any]],
        asset_hint: str,
        standards: list[str],
        freeform_notes: str,
        upload_summaries: list[str],
        research_findings: list[dict[str, Any]] | None = None,
        workforce_signals: list[str] | None = None,
    ) -> dict[str, Any]:
        purpose = purpose if purpose in ALLOWED_PURPOSES else "freeform"
        scopes = [s for s in scopes if s in ALLOWED_SCOPES]
        standards = [s for s in standards if s in ALLOWED_STANDARDS]

        themes = await self._collect_platform_themes(tenant_id, scopes, case_refs, asset_hint)
        if workforce_signals:
            themes.extend(workforce_signals)

        research = research_findings or []
        brief_id = str(uuid4())
        proposed_sections = self._propose_sections(purpose, standards, themes, asset_hint)
        open_questions = self._default_open_questions(purpose)

        return {
            "brief_id": brief_id,
            "purpose": purpose,
            "scopes": scopes,
            "case_refs": case_refs[:20],
            "asset_hint": (asset_hint or "")[:200],
            "standards": standards,
            "themes": themes[:40],
            "upload_summaries": [u[:500] for u in upload_summaries[:10]],
            "research_findings": research[:15],
            "research_available": bool(research),
            "proposed_sections": proposed_sections,
            "open_questions": open_questions,
            "freeform_notes": (freeform_notes or "")[:2000],
            "qa_answers": {},
        }

    def apply_qa_answers(self, brief: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
        out = dict(brief)
        cleaned = {str(k)[:80]: str(v)[:1000] for k, v in (answers or {}).items()}
        out["qa_answers"] = cleaned
        # Refine proposed sections from answers when user lists themes
        include = cleaned.get("include_themes") or cleaned.get("extra_themes")
        if include:
            sections = list(out.get("proposed_sections") or [])
            sections.append(
                {
                    "title": "User-requested themes",
                    "rationale": include[:300],
                }
            )
            out["proposed_sections"] = sections[:12]
        return out

    async def find_similar_templates(
        self,
        *,
        tenant_id: int,
        brief: dict[str, Any],
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        from src.domain.models.audit import AuditTemplate

        hay = " ".join(
            [
                str(brief.get("purpose") or ""),
                str(brief.get("asset_hint") or ""),
                str(brief.get("freeform_notes") or ""),
                " ".join(brief.get("standards") or []),
                " ".join(brief.get("themes") or []),
                " ".join(s.get("title", "") for s in (brief.get("proposed_sections") or [])),
            ]
        )
        from src.domain.models.audit import AuditSection

        stmt = (
            select(AuditTemplate)
            .options(selectinload(AuditTemplate.sections).selectinload(AuditSection.questions))
            .where(
                AuditTemplate.tenant_id == tenant_id,
                AuditTemplate.is_active.is_(True),
                AuditTemplate.archived_at.is_(None),
            )
            .order_by(AuditTemplate.updated_at.desc())
            .limit(80)
        )

        rows = (await self.db.execute(stmt)).scalars().all()
        scored: list[dict[str, Any]] = []
        for tmpl in rows:
            qtitles = []
            for sec in getattr(tmpl, "sections", None) or []:
                for q in getattr(sec, "questions", None) or []:
                    if getattr(q, "text", None):
                        qtitles.append(str(q.text)[:120])
            blob = f"{tmpl.name or ''} {tmpl.description or ''} {tmpl.category or ''} {' '.join(qtitles[:30])}"
            score = _overlap_score(hay, blob)
            if score < 0.18:
                continue
            scored.append(
                {
                    "id": tmpl.id,
                    "name": tmpl.name,
                    "description": (tmpl.description or "")[:300],
                    "category": tmpl.category,
                    "audit_type": tmpl.audit_type,
                    "score": round(score, 3),
                    "question_sample": qtitles[:5],
                }
            )
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:limit]

    def compose_generation_prompt(self, brief: dict[str, Any]) -> str:
        purpose = brief.get("purpose") or "freeform"
        asset = brief.get("asset_hint") or "general workplace"
        standards = ", ".join(brief.get("standards") or []) or "good industry practice"
        themes = "; ".join(brief.get("themes") or [])[:1500]
        uploads = "\n".join(f"- {u}" for u in (brief.get("upload_summaries") or [])[:8])
        research_lines = []
        for f in brief.get("research_findings") or []:
            title = f.get("title") or "Finding"
            url = f.get("source_url") or ""
            summary = f.get("summary") or ""
            research_lines.append(f"- {title}: {summary[:240]} ({url})")
        research = (
            "\n".join(research_lines) or "(no live research available — use model knowledge only and mark as such)"
        )
        qa = brief.get("qa_answers") or {}
        qa_txt = "\n".join(f"- {k}: {v}" for k, v in qa.items()) or "(none)"
        sections = ", ".join(s.get("title", "") for s in (brief.get("proposed_sections") or []))
        case_bits = ", ".join(f"{c.get('type')}:{c.get('id')}" for c in (brief.get("case_refs") or []) if c.get("id"))
        convert_note = ""
        if purpose == "technical_assessment":
            convert_note = (
                "Structure as a competency/supervisor assessment with skill criteria, "
                "pass/fail guidance, and evidence of competence — not only equipment condition checks.\n"
            )

        return f"""Generate a best-practice audit/assessment template.

Purpose: {purpose}
Asset / subject: {asset}
Standards to align with: {standards}
Linked risk cases: {case_bits or 'none'}
Platform themes / risk signals: {themes or 'none'}
Proposed section outline: {sections or 'decide best structure'}
{convert_note}
Upload / job-sheet summaries:
{uploads or '(none)'}

External research (cite in guidance notes where used):
{research}

Clarifying answers from the user:
{qa_txt}

Additional notes: {brief.get('freeform_notes') or ''}

Requirements:
- Mix mandatory (essential) and nice-to-have items where the user requested both.
- Include clear scoring/question types suitable for field use.
- Reference ISO/UVDB/Planet Mark/HSE themes in isoClause or guidance when relevant.
- Do not invent URLs; only cite research sources listed above.
"""

    async def _collect_platform_themes(
        self,
        tenant_id: int,
        scopes: list[str],
        case_refs: list[dict[str, Any]],
        asset_hint: str,
    ) -> list[str]:
        themes: list[str] = []
        for ref in case_refs[:10]:
            themes.append(await self._theme_from_case(tenant_id, ref))

        try:
            if "incidents" in scopes:
                themes.extend(await self._recent_incident_titles(tenant_id, asset_hint))
            if "near_misses" in scopes:
                themes.extend(await self._recent_near_miss_titles(tenant_id, asset_hint))
            if "rtas" in scopes:
                themes.extend(await self._recent_rta_titles(tenant_id))
            if "complaints" in scopes:
                themes.extend(await self._recent_complaint_titles(tenant_id))
            if "documents" in scopes and asset_hint:
                themes.extend(await self._semantic_doc_themes(tenant_id, asset_hint))
            themes.extend(await self._latest_safety_insight_themes(tenant_id))
        except Exception as exc:  # noqa: BLE001 — fail-closed
            logger.info("Audit builder platform theme gather degraded: %s", type(exc).__name__)
        return [t for t in themes if t][:40]

    async def _latest_safety_insight_themes(self, tenant_id: int) -> list[str]:
        """Merge persisted Safety Insights micro-themes into Audit Builder briefs."""
        try:
            from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService

            service = SafetyInsightsAnalystService(self.db)
            run = await service.latest_succeeded(tenant_id)
            if run is None:
                return []
            payload = await service.serialize_run(run, include_children=True)
            out: list[str] = []
            for theme in (payload.get("micro_themes") or [])[:12]:
                label = str(theme.get("label") or "").strip()
                if not label:
                    continue
                refs = ", ".join(
                    str(r.get("reference_number") or "")
                    for r in (theme.get("case_refs") or [])[:6]
                    if r.get("reference_number")
                )
                out.append(
                    f"Safety Insight: {label} (n={theme.get('case_count')}"
                    + (f"; {refs}" if refs else "")
                    + ")"
                )
            return out
        except Exception as exc:  # noqa: BLE001
            logger.info("Safety insight theme merge skipped: %s", type(exc).__name__)
            return []

    async def _theme_from_case(self, tenant_id: int, ref: dict[str, Any]) -> str:
        ctype = str(ref.get("type") or "").lower()
        raw_id = ref.get("id")
        if raw_id is None:
            return ""
        try:
            cid = int(raw_id)
        except (TypeError, ValueError):
            return ""
        try:
            if ctype == "incident":
                from src.domain.models.incident import Incident

                incident = (
                    await self.db.execute(select(Incident).where(Incident.tenant_id == tenant_id, Incident.id == cid))
                ).scalar_one_or_none()
                if incident:
                    return f"Incident {incident.reference_number}: {(incident.title or '')[:120]}"
            if ctype in {"near_miss", "near-miss", "nearmiss"}:
                from src.domain.models.near_miss import NearMiss

                near_miss = (
                    await self.db.execute(select(NearMiss).where(NearMiss.tenant_id == tenant_id, NearMiss.id == cid))
                ).scalar_one_or_none()
                if near_miss:
                    return f"Near miss {near_miss.reference_number}: {(near_miss.description or '')[:120]}"
            if ctype == "rta":
                from src.domain.models.rta import RTA

                rta = (
                    await self.db.execute(select(RTA).where(RTA.tenant_id == tenant_id, RTA.id == cid))
                ).scalar_one_or_none()
                if rta:
                    return f"RTA {rta.reference_number}: {(rta.description or '')[:120]}"
            if ctype == "complaint":
                from src.domain.models.complaint import Complaint

                complaint = (
                    await self.db.execute(
                        select(Complaint).where(Complaint.tenant_id == tenant_id, Complaint.id == cid)
                    )
                ).scalar_one_or_none()
                if complaint:
                    return (
                        f"Complaint {complaint.reference_number}: "
                        f"{(complaint.description or complaint.title or '')[:120]}"
                    )
        except Exception as exc:  # noqa: BLE001
            logger.info("Case theme load failed: %s", type(exc).__name__)
        return ""

    async def _recent_incident_titles(self, tenant_id: int, asset_hint: str) -> list[str]:
        from src.domain.models.incident import Incident

        stmt = select(Incident).where(Incident.tenant_id == tenant_id).order_by(Incident.created_at.desc()).limit(8)
        if asset_hint:
            pattern = f"%{asset_hint[:80]}%"
            stmt = stmt.where(or_(Incident.title.ilike(pattern), Incident.description.ilike(pattern)))
        rows = (await self.db.execute(stmt)).scalars().all()
        return [f"Recent incident: {(r.title or r.reference_number)[:100]}" for r in rows]

    async def _recent_near_miss_titles(self, tenant_id: int, asset_hint: str) -> list[str]:
        from src.domain.models.near_miss import NearMiss

        stmt = select(NearMiss).where(NearMiss.tenant_id == tenant_id).order_by(NearMiss.created_at.desc()).limit(8)
        if asset_hint:
            pattern = f"%{asset_hint[:80]}%"
            stmt = stmt.where(NearMiss.description.ilike(pattern))
        rows = (await self.db.execute(stmt)).scalars().all()
        return [f"Recent near miss: {(r.description or r.reference_number)[:100]}" for r in rows]

    async def _recent_rta_titles(self, tenant_id: int) -> list[str]:
        from src.domain.models.rta import RTA

        rows = (
            (
                await self.db.execute(
                    select(RTA).where(RTA.tenant_id == tenant_id).order_by(RTA.created_at.desc()).limit(5)
                )
            )
            .scalars()
            .all()
        )
        return [f"Recent RTA: {(r.location or r.reference_number)[:100]}" for r in rows]

    async def _recent_complaint_titles(self, tenant_id: int) -> list[str]:
        from src.domain.models.complaint import Complaint

        rows = (
            (
                await self.db.execute(
                    select(Complaint)
                    .where(Complaint.tenant_id == tenant_id)
                    .order_by(Complaint.created_at.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )
        return [f"Recent complaint: {(getattr(r, 'title', None) or r.reference_number)[:100]}" for r in rows]

    async def _semantic_doc_themes(self, tenant_id: int, asset_hint: str) -> list[str]:
        try:
            from src.domain.services.vector_search_service import VectorSearchService

            svc = VectorSearchService(self.db)
            hits = await svc.search(query=asset_hint[:200], tenant_id=tenant_id, limit=5)
            out = []
            for h in hits or []:
                title = h.get("title") if isinstance(h, dict) else getattr(h, "title", None)
                if title:
                    out.append(f"Library doc: {str(title)[:100]}")
            return out
        except Exception as exc:  # noqa: BLE001
            logger.info("Semantic doc themes unavailable: %s", type(exc).__name__)
            return []

    @staticmethod
    def _propose_sections(
        purpose: str,
        standards: list[str],
        themes: list[str],
        asset_hint: str,
    ) -> list[dict[str, str]]:
        base = [
            {"title": "Scope and preparation", "rationale": "Define boundaries and pre-checks"},
            {"title": "Critical controls", "rationale": "Highest-risk controls first"},
            {"title": "Evidence and records", "rationale": "Document what good looks like"},
            {"title": "Findings and follow-up", "rationale": "CAPA and close-out"},
        ]
        if purpose == "technical_assessment":
            base.insert(1, {"title": "Competency demonstration", "rationale": "Observe skills end-to-end"})
        if purpose == "vehicle_asset_check" or asset_hint:
            base.insert(
                1,
                {
                    "title": f"Asset-specific checks ({asset_hint or 'vehicle/plant'})",
                    "rationale": "OEM / job sheet steps",
                },
            )
        if any("27001" in s or "ISO 27001" in s for s in standards):
            base.insert(1, {"title": "Information security controls", "rationale": "ISO 27001 alignment"})
        if themes:
            base.insert(2, {"title": "Lessons from recent cases", "rationale": "Address platform risk signals"})
        return base[:8]

    @staticmethod
    def _default_open_questions(purpose: str) -> list[dict[str, str]]:
        qs = [
            {
                "id": "depth",
                "prompt": "How deep should this be — quick checklist, full audit, or competency assessment?",
            },
            {
                "id": "mandatory_split",
                "prompt": "Should we include both mandatory and nice-to-have items?",
            },
            {
                "id": "roles",
                "prompt": "Who is being assessed or audited (engineer, supervisor, site team)?",
            },
            {
                "id": "include_themes",
                "prompt": "Any themes from recent incidents/near misses that must be included?",
            },
        ]
        if purpose == "technical_assessment":
            qs.append(
                {
                    "id": "scoring",
                    "prompt": "Preferred scoring model (pass/fail, 1–5 scale, weighted essential items)?",
                }
            )
        return qs[:6]

    async def workforce_signals(self, tenant_id: int, asset_hint: str) -> list[str]:
        """Best-effort competence/training signals for technical assessments."""
        signals: list[str] = []
        try:
            from src.domain.models.engineer import Engineer

            stmt = select(Engineer).where(Engineer.tenant_id == tenant_id).limit(5)
            rows = (await self.db.execute(stmt)).scalars().all()
            for eng in rows:
                name = (
                    getattr(eng, "full_name", None)
                    or getattr(eng, "name", None)
                    or getattr(eng, "display_name", None)
                    or f"engineer:{eng.id}"
                )
                signals.append(f"Workforce sample: {name}")
            if asset_hint:
                signals.append(f"Target competence domain: {asset_hint[:120]}")
        except Exception as exc:  # noqa: BLE001
            logger.info("Workforce signals unavailable: %s", type(exc).__name__)
        return signals[:10]
