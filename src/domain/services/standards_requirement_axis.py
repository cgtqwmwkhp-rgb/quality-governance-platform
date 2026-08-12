"""Int-W5 requirement axes — catalogues that are NOT alignment coverage.

A requirement axis answers: "what does this scheme/framework ask for?".
It deliberately does **not** answer: "may evidence from another framework
serve this cell?" That remains TrapGuard ``covers_framework`` / imported
edges (W4 honesty; W6 will add EXACT/NEAR pairs).

Isolation
---------
``standards_trap_guard`` and ``standards_ingest_gate`` must never import this
module. Catalogue presence must not flip framed-token matching or auto-confirm.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from src.domain.services.standards_trap_guard import clause_key
from src.domain.uvdb.protocol_b2_v118 import UVDB_B2_SECTIONS

logger = logging.getLogger(__name__)

_SPEC_PATH = (
    Path(__file__).resolve().parents[3] / "specs" / "standards" / "requirement-axes-v1.json"
)

# Framework ids that ship an own-axis catalogue in this wave (excl. ISO 22301 —
# that lives in ALL_CLAUSES / ISOStandard).
SCHEME_AXIS_FRAMEWORKS = frozenset({"ce", "cep", "chas", "ssip", "iip", "uvdb", "pm"})


@lru_cache(maxsize=1)
def _load_spec() -> dict[str, Any]:
    raw = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "axes" not in raw:
        raise RuntimeError(f"Malformed requirement axes spec: {_SPEC_PATH}")
    return raw


def requirement_catalogue_key(framework: str, clause_number: str) -> str:
    """Same formula as TrapGuard / alignment import — never hand-author keys."""
    return clause_key(framework, clause_number)


def _uvdb_axis() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for section in UVDB_B2_SECTIONS:
        number = str(section.get("number") or "").strip()
        if not number:
            continue
        status = str(section.get("content_status") or "pending_protocol_pdf")
        rows.append(
            {
                "clause_number": f"UVDB {number}",
                "title": str(section.get("title") or f"UVDB section {number}"),
                "level": 1,
                "content_status": status,
                "catalogue_key": requirement_catalogue_key("uvdb", f"UVDB {number}"),
            }
        )
        if status != "loaded":
            continue
        for question in section.get("questions") or []:
            qn = str(question.get("number") or "").strip()
            if not qn:
                continue
            rows.append(
                {
                    "clause_number": f"UVDB {qn}",
                    "title": str(question.get("text") or f"UVDB {qn}")[:300],
                    "level": 2,
                    "content_status": "loaded",
                    "catalogue_key": requirement_catalogue_key("uvdb", f"UVDB {qn}"),
                }
            )
    return {
        "framework": "uvdb",
        "standard_code": "UVDB_B2",
        "source_ref": "UVDB-QS-003 (protocol_b2_v118 SSOT)",
        "source_url": None,
        "source_version": "11.8-target",
        "numbering_source": "source",
        "content_status": "partial",
        "rows": rows,
    }


def _axis_from_spec(framework: str, body: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for raw in body.get("rows") or []:
        clause_number = str(raw.get("clause_number") or "").strip()
        if not clause_number:
            continue
        rows.append(
            {
                "clause_number": clause_number,
                "title": str(raw.get("title") or clause_number)[:300],
                "level": int(raw.get("level") or 1),
                "content_status": str(raw.get("content_status") or body.get("content_status") or "provisional"),
                "catalogue_key": requirement_catalogue_key(framework, clause_number),
            }
        )
    return {
        "framework": framework,
        "standard_code": body.get("standard_code"),
        "source_ref": body.get("source_ref"),
        "source_url": body.get("source_url"),
        "source_version": body.get("source_version"),
        "numbering_source": body.get("numbering_source"),
        "content_status": body.get("content_status"),
        "rows": rows,
    }


@lru_cache(maxsize=1)
def all_requirement_axes() -> dict[str, dict[str, Any]]:
    """framework → axis payload (includes derived UVDB)."""
    spec = _load_spec()
    out: dict[str, dict[str, Any]] = {}
    for framework, body in (spec.get("axes") or {}).items():
        fw = str(framework).strip().lower()
        if fw == "constructionline":
            continue
        out[fw] = _axis_from_spec(fw, body if isinstance(body, dict) else {})
    out["uvdb"] = _uvdb_axis()
    return out


def has_requirement_axis(framework: str) -> bool:
    """True when a W5 catalogue exists for this framework id."""
    fw = str(framework or "").strip().lower()
    if fw == "22301":
        # First-class ISO — axis is ALL_CLAUSES, not this module's scheme axes.
        return True
    return fw in all_requirement_axes()


def axis_rows(framework: str) -> list[dict[str, Any]]:
    fw = str(framework or "").strip().lower()
    axis = all_requirement_axes().get(fw)
    if axis is None:
        return []
    return list(axis.get("rows") or [])


def requirement_axes_payload(
    *,
    alignment_clause_keys: Optional[set[str]] = None,
) -> dict[str, Any]:
    """API block for alignment catalogue — dedupes keys already on alignment rows."""
    owned = alignment_clause_keys or set()
    axes_out: dict[str, Any] = {}
    for fw, axis in all_requirement_axes().items():
        kept = []
        for row in axis.get("rows") or []:
            key = row["catalogue_key"]
            if key in owned:
                continue
            kept.append(row)
        axes_out[fw] = {
            **{k: v for k, v in axis.items() if k != "rows"},
            "rows": kept,
            "row_count": len(kept),
            "deduped_against_alignment": len(axis.get("rows") or []) - len(kept),
        }
    return {
        "spec_ref": _load_spec().get("spec_ref"),
        "version_label": _load_spec().get("version_label"),
        "axes": axes_out,
        "honesty_note": (
            "Requirement axes list what each scheme asks for. They do not create "
            "alignment EXACT peers or auto-confirm rights. Cross-framework share "
            "remains edge-driven (W6)."
        ),
    }


def build_scheme_requirement_clause_plans(
    code_to_standard_id: dict[str, int],
) -> list[dict[str, Any]]:
    """Plan ``clauses`` inserts for scheme axes (idempotent by catalogue_key)."""
    plans: list[dict[str, Any]] = []
    sort_base = 0
    for fw, axis in all_requirement_axes().items():
        code = str(axis.get("standard_code") or "")
        standard_id = code_to_standard_id.get(code)
        if standard_id is None:
            logger.warning("Skipping axis %s — no standards.id for code %s", fw, code)
            continue
        for index, row in enumerate(axis.get("rows") or []):
            plans.append(
                {
                    "standard_id": standard_id,
                    "catalogue_key": row["catalogue_key"],
                    "clause_number": str(row["clause_number"])[:20],
                    "title": str(row["title"])[:300],
                    "description": (
                        f"source={axis.get('source_ref')}; "
                        f"status={row.get('content_status')}"
                    ),
                    "level": int(row.get("level") or 1),
                    "sort_order": sort_base + index,
                    "is_active": True,
                    "parent_catalogue_key": None,
                    "kind": "requirement",
                }
            )
        sort_base += 1000
    return plans
