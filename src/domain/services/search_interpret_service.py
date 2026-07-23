"""Natural-language search interpret: rules first, Gemini JSON second, fail-closed."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

ALLOWED_MODULES = {
    "Incidents",
    "RTAs",
    "Complaints",
    "Risks",
    "Audits",
    "Actions",
    "Documents",
}

# Phrase → structured intent (checked before LLM).
_RULE_PATTERNS: list[tuple[re.Pattern[str], dict[str, Any]]] = [
    (
        re.compile(r"\b(overdue\s+actions?|actions?\s+overdue)\b", re.I),
        {
            "q": "action",
            "module": "Actions",
            "status": "overdue,open",
            "navigate": "/actions?view=my_overdue",
            "label": "Overdue actions",
            "source": "rules",
        },
    ),
    (
        re.compile(r"\b(high[- ]?priority|critical)\s+incidents?\b|\bincidents?\s+(high|critical)\b", re.I),
        {
            "q": "incident",
            "module": "Incidents",
            "status": "open,reported,under_investigation",
            "label": "High-priority incidents",
            "source": "rules",
        },
    ),
    (
        re.compile(r"\b(pending|open|scheduled)\s+(iso\s+)?audits?\b|\baudits?\s+(this\s+month|pending)\b", re.I),
        {
            "q": "audit",
            "module": "Audits",
            "status": "open,pending,scheduled,in_progress",
            "date_range": "month",
            "label": "Pending audits this month",
            "source": "rules",
        },
    ),
    (
        re.compile(r"\b(unresolved|open)\s+(customer\s+)?complaints?\b|\bcomplaints?\s+(open|unresolved)\b", re.I),
        {
            "q": "complaint",
            "module": "Complaints",
            "status": "open,received,under_investigation,in_progress",
            "label": "Unresolved complaints",
            "source": "rules",
        },
    ),
]


def _month_bounds(today: Optional[date] = None) -> tuple[str, str]:
    day = today or date.today()
    start = day.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1, day=1) - timedelta(days=1)
    return start.isoformat(), end.isoformat()


def apply_date_range(intent: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    """Expand date_range tokens into date_from/date_to ISO dates."""
    out = dict(intent)
    token = out.pop("date_range", None)
    day = today or date.today()
    if token == "today":
        out["date_from"] = day.isoformat()
        out["date_to"] = day.isoformat()
    elif token == "week":
        out["date_from"] = (day - timedelta(days=7)).isoformat()
        out["date_to"] = day.isoformat()
    elif token == "month":
        out["date_from"], out["date_to"] = _month_bounds(day)
    return out


def interpret_with_rules(query: str) -> Optional[dict[str, Any]]:
    text = (query or "").strip()
    if not text:
        return None
    for pattern, intent in _RULE_PATTERNS:
        if pattern.search(text):
            return apply_date_range(dict(intent))
    return None


def validate_intent(raw: dict[str, Any], *, fallback_q: str) -> dict[str, Any]:
    """Allowlist-validate model/rule output."""
    q = str(raw.get("q") or fallback_q or "").strip()[:200] or fallback_q
    module = raw.get("module")
    if module is not None:
        module = str(module)
        if module not in ALLOWED_MODULES:
            module = None
    status = raw.get("status")
    if status is not None:
        status = str(status)[:120]
    date_from = raw.get("date_from")
    date_to = raw.get("date_to")
    if date_from is not None:
        date_from = str(date_from)[:10]
    if date_to is not None:
        date_to = str(date_to)[:10]
    navigate = raw.get("navigate")
    if navigate is not None:
        navigate = str(navigate)
        if not navigate.startswith("/"):
            navigate = None
    label = raw.get("label")
    source = str(raw.get("source") or "keyword")
    return {
        "q": q,
        "module": module,
        "status": status,
        "date_from": date_from,
        "date_to": date_to,
        "navigate": navigate,
        "label": label,
        "source": source,
    }


async def interpret_with_gemini(query: str) -> Optional[dict[str, Any]]:
    """Ask Gemini for structured search filters; return None on any failure."""
    try:
        import asyncio

        from src.domain.services.gemini_ai_service import GEMINI_MODEL, GeminiAIService, _GEMINI_AI_UPSTREAM_BREAKER
        from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

        service = GeminiAIService()
        client = service._get_client()  # noqa: SLF001 — shared client factory
        if not client:
            return None

        prompt = f"""Convert this workplace quality-governance search request into JSON only.
Allowed modules: Incidents, RTAs, Complaints, Risks, Audits, Actions, Documents.
Return object keys: q (keywords), module (or null), status (comma-separated or null),
date_from (YYYY-MM-DD or null), date_to (YYYY-MM-DD or null), label (short human label).
No markdown. Query: {query!r}"""

        def _run() -> str:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return response.text or ""

        text = await call_via_upstream_breaker(_GEMINI_AI_UPSTREAM_BREAKER, asyncio.to_thread, _run)
        text = (text or "").strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        data["source"] = "gemini"
        return validate_intent(data, fallback_q=query)
    except Exception as exc:  # noqa: BLE001 — fail-closed for search UX
        logger.info("Search interpret Gemini unavailable: %s", type(exc).__name__)
        return None


async def interpret_search_query(query: str) -> dict[str, Any]:
    """Rules → Gemini → keyword fallback."""
    q = (query or "").strip()
    ruled = interpret_with_rules(q)
    if ruled:
        return validate_intent(ruled, fallback_q=q)

    looks_nl = bool(re.search(r"\b(show|find|list|all|pending|overdue|unresolved|recent)\b", q, re.I)) or " " in q
    if looks_nl:
        gemini = await interpret_with_gemini(q)
        if gemini:
            return gemini

    return validate_intent({"q": q, "source": "keyword"}, fallback_q=q)
