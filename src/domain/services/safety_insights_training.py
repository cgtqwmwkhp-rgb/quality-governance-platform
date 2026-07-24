"""Lightweight training / competence correlation signals for Safety Insights deep-runs.

Honest-empty: never invents overlaps. When competence/training data is sparse or
unrelated to theme labels, returns ``available=False`` and ``signals=[]``.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "by",
        "for",
        "from",
        "in",
        "into",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
        "near",
        "miss",
        "incident",
        "rta",
        "complaint",
        "case",
        "theme",
    }
)

_OPEN_GAP_STATUSES = frozenset({"open", "linked", "capa_created"})
_DUE_COMPETENCY_STATES = frozenset({"due", "expired", "failed"})
_EXPIRED_TICKET_STATES = frozenset({"expired"})


def tokenize_label(text: str) -> set[str]:
    """Lowercase alphanumeric tokens ≥3 chars, minus stopwords."""
    if not text:
        return set()
    tokens = {t for t in re.findall(r"[a-z0-9]{3,}", text.lower())}
    return {t for t in tokens if t not in _STOPWORDS}


def labels_overlap(theme_label: str, candidate: str, *, min_shared: int = 1) -> set[str]:
    """Return shared tokens between a theme label and a competence/training string."""
    shared = tokenize_label(theme_label) & tokenize_label(candidate)
    if len(shared) < min_shared:
        return set()
    return shared


def empty_training_signals(*, reason: str = "no_competence_or_training_data") -> dict[str, Any]:
    return {
        "available": False,
        "signals": [],
        "reason": reason,
        "sources_checked": [
            "competence_gap_actions",
            "training_tickets",
            "competency_records",
            "competency_requirements",
        ],
    }


def _status_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value.value if hasattr(value, "value") else value).strip().lower()


def _match_theme(theme_labels: Iterable[str], haystack: str) -> Optional[tuple[str, set[str]]]:
    best: Optional[tuple[str, set[str]]] = None
    for label in theme_labels:
        shared = labels_overlap(label, haystack)
        if not shared:
            continue
        if best is None or len(shared) > len(best[1]):
            best = (label, shared)
    return best


def build_signals_from_rows(
    *,
    theme_labels: list[str],
    modules: list[str],
    gaps: list[Any],
    tickets: list[Any],
    competency_rows: list[Any],
    requirements: list[Any],
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Pure builder used by the async correlator and unit tests (no DB)."""
    del modules  # reserved for future module-scoped filtering; honesty over invention
    current = now or datetime.now(timezone.utc)
    signals: list[dict[str, Any]] = []
    labels = [lbl for lbl in theme_labels if (lbl or "").strip()]

    req_by_id = {getattr(r, "id", None): r for r in requirements if getattr(r, "id", None) is not None}

    for gap in gaps:
        status = _status_value(getattr(gap, "status", None))
        if status not in _OPEN_GAP_STATUSES:
            continue
        scheme = (getattr(gap, "ticket_scheme", None) or "").strip()
        rationale = (getattr(gap, "rationale", None) or "").strip()
        haystack = " ".join(part for part in (scheme, rationale) if part)
        match = _match_theme(labels, haystack) if haystack and labels else None
        # Open gaps are real evidence even without theme token overlap.
        theme_label = match[0] if match else None
        shared = sorted(match[1]) if match else []
        req = req_by_id.get(getattr(gap, "requirement_id", None))
        req_name = (getattr(req, "name", None) or "").strip() if req else ""
        summary_bits = ["Open competence gap"]
        if scheme:
            summary_bits.append(f"scheme={scheme}")
        if req_name:
            summary_bits.append(f"requirement={req_name}")
        if theme_label:
            summary_bits.append(f"overlaps theme '{theme_label}'")
        signals.append(
            {
                "kind": "open_competence_gap",
                "theme_label": theme_label,
                "shared_tokens": shared,
                "summary": "; ".join(summary_bits),
                "evidence": {
                    "gap_id": getattr(gap, "id", None),
                    "status": status,
                    "signal_type": _status_value(getattr(gap, "signal_type", None)),
                    "ticket_scheme": scheme or None,
                    "requirement_id": getattr(gap, "requirement_id", None),
                    "engineer_id": getattr(gap, "engineer_id", None),
                },
                "strength": "moderate" if shared else "weak",
            }
        )

    for ticket in tickets:
        scheme = (getattr(ticket, "scheme", None) or "").strip()
        verify = _status_value(getattr(ticket, "verify_state", None))
        expires_at = getattr(ticket, "expires_at", None)
        expired_by_date = False
        if isinstance(expires_at, datetime):
            exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
            expired_by_date = exp < current
        is_expired = verify in _EXPIRED_TICKET_STATES or expired_by_date
        if not is_expired and not scheme:
            continue
        match = _match_theme(labels, scheme) if scheme and labels else None
        # Only emit ticket signals when expired/due OR theme overlap exists.
        if not is_expired and match is None:
            continue
        theme_label = match[0] if match else None
        shared = sorted(match[1]) if match else []
        kind = "expired_training_ticket" if is_expired else "scheme_theme_overlap"
        summary = f"Training ticket scheme '{scheme}'" if scheme else "Training ticket"
        if is_expired:
            summary += " is expired/overdue"
        if theme_label:
            summary += f"; overlaps theme '{theme_label}'"
        signals.append(
            {
                "kind": kind,
                "theme_label": theme_label,
                "shared_tokens": shared,
                "summary": summary,
                "evidence": {
                    "ticket_id": getattr(ticket, "id", None),
                    "scheme": scheme or None,
                    "verify_state": verify or None,
                    "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else None,
                    "engineer_id": getattr(ticket, "engineer_id", None),
                },
                "strength": "moderate" if (is_expired and shared) else ("moderate" if is_expired else "weak"),
            }
        )

    for row in competency_rows:
        state = _status_value(getattr(row, "state", None))
        if state not in _DUE_COMPETENCY_STATES:
            continue
        # Optional denormalised name for tests / future joins — never invent.
        req_name = (getattr(row, "requirement_name", None) or "").strip()
        if not req_name:
            req2 = req_by_id.get(getattr(row, "requirement_id", None))
            if req2 is not None:
                req_name = (getattr(req2, "name", None) or "").strip()
        match = _match_theme(labels, req_name) if req_name and labels else None
        theme_label = match[0] if match else None
        shared = sorted(match[1]) if match else []
        summary = f"Competency record {state}"
        if req_name:
            summary += f" ({req_name})"
        if theme_label:
            summary += f"; overlaps theme '{theme_label}'"
        signals.append(
            {
                "kind": "due_or_expired_competency",
                "theme_label": theme_label,
                "shared_tokens": shared,
                "summary": summary,
                "evidence": {
                    "competency_record_id": getattr(row, "id", None),
                    "state": state,
                    "outcome": getattr(row, "outcome", None),
                    "engineer_id": getattr(row, "engineer_id", None),
                    "requirement_name": req_name or None,
                },
                "strength": "moderate" if shared else "weak",
            }
        )

    # Requirement names that overlap themes (even without open gaps / due records).
    seen_req_ids: set[Any] = set()
    for req in requirements:
        req_id = getattr(req, "id", None)
        name = (getattr(req, "name", None) or "").strip()
        if not name or not labels:
            continue
        match = _match_theme(labels, name)
        if match is None:
            continue
        if req_id is not None and req_id in seen_req_ids:
            continue
        if req_id is not None:
            seen_req_ids.add(req_id)
        theme_label, shared = match[0], sorted(match[1])
        signals.append(
            {
                "kind": "requirement_theme_overlap",
                "theme_label": theme_label,
                "shared_tokens": shared,
                "summary": f"Competency requirement '{name}' overlaps theme '{theme_label}'",
                "evidence": {
                    "requirement_id": req_id,
                    "requirement_name": name,
                    "is_mandatory": bool(getattr(req, "is_mandatory", False)),
                },
                "strength": "weak",
            }
        )

    if not signals:
        return empty_training_signals(reason="no_matching_competence_or_training_signals")

    # Cap payload size; prefer theme-linked then expired/open evidence.
    def _rank(sig: dict[str, Any]) -> tuple[int, int]:
        strength = 1 if sig.get("strength") == "moderate" else 0
        themed = 1 if sig.get("theme_label") else 0
        return (strength + themed, themed)

    signals.sort(key=_rank, reverse=True)
    capped = signals[:25]
    return {
        "available": True,
        "signals": capped,
        "reason": None,
        "signal_count": len(capped),
        "sources_checked": [
            "competence_gap_actions",
            "training_tickets",
            "competency_records",
            "competency_requirements",
        ],
    }


async def correlate_training_signals(
    db: AsyncSession,
    *,
    tenant_id: int,
    theme_labels: Optional[list[str]] = None,
    modules: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Query competence/training models and return honest correlation signals."""
    labels = [str(x).strip() for x in (theme_labels or []) if str(x).strip()]
    module_list = [str(m).strip().lower() for m in (modules or []) if str(m).strip()]

    try:
        from src.domain.models.competence_gap import CompetenceGapAction
        from src.domain.models.engineer import CompetencyRecord, CompetencyRequirement, TrainingTicket
    except Exception as exc:  # noqa: BLE001
        logger.info("Training models unavailable: %s", type(exc).__name__)
        return empty_training_signals(reason="training_models_unavailable")

    try:
        gaps = list(
            (
                await db.execute(
                    select(CompetenceGapAction)
                    .where(CompetenceGapAction.tenant_id == tenant_id)
                    .order_by(CompetenceGapAction.created_at.desc())
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        tickets = list(
            (
                await db.execute(
                    select(TrainingTicket)
                    .where(TrainingTicket.tenant_id == tenant_id)
                    .order_by(TrainingTicket.id.desc())
                    .limit(150)
                )
            )
            .scalars()
            .all()
        )
        competency_rows = list(
            (
                await db.execute(
                    select(CompetencyRecord)
                    .where(CompetencyRecord.tenant_id == tenant_id)
                    .order_by(CompetencyRecord.id.desc())
                    .limit(150)
                )
            )
            .scalars()
            .all()
        )
        requirements = list(
            (
                await db.execute(
                    select(CompetencyRequirement)
                    .where(CompetencyRequirement.tenant_id == tenant_id)
                    .order_by(CompetencyRequirement.id.desc())
                    .limit(150)
                )
            )
            .scalars()
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Training correlation query failed: %s", type(exc).__name__)
        return empty_training_signals(reason=f"query_failed:{type(exc).__name__}")

    if not gaps and not tickets and not competency_rows and not requirements:
        return empty_training_signals(reason="no_competence_or_training_data")

    return build_signals_from_rows(
        theme_labels=labels,
        modules=module_list,
        gaps=gaps,
        tickets=tickets,
        competency_rows=competency_rows,
        requirements=requirements,
    )
