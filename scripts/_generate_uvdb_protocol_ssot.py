"""One-off generator for src/domain/uvdb/protocol_b2_v118.py from routes SSOT."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HEADER = '''"""UVDB Verify B2 protocol single source of truth (v11.8 target).

Loaded question text is sourced from the prior V11.2 static extract for sections
1, 2, and 12-15. Sections 3-11 are structural shells only until the official
UVDB-QS-003 v11.8 protocol PDF is ingested (Wave 2).
"""

from __future__ import annotations

from typing import Any

PROTOCOL_VERSION = "11.8-target"
PROTOCOL_REFERENCE = "UVDB-QS-003"
PROTOCOL_NAME = "UVDB Verify B2 Audit Protocol"
PROTOCOL_DESCRIPTION = "Comprehensive supply chain qualification audit for UK utilities sector"
TOTAL_SECTIONS = 15
LOADED_SECTION_NUMBERS = ("1", "2", "12", "13", "14", "15")
PENDING_SECTION_NUMBERS = ("3", "4", "5", "6", "7", "8", "9", "10", "11")


def _count_questions(sections: list[dict[str, Any]]) -> int:
    return sum(len(section.get("questions") or []) for section in sections)


def build_content_coverage() -> dict[str, Any]:
    """Honest coverage summary for API/FE consumers."""
    loaded_question_count = _count_questions(
        [s for s in UVDB_B2_SECTIONS if s.get("content_status") == "loaded"]
    )
    pending_question_count = _count_questions(
        [s for s in UVDB_B2_SECTIONS if s.get("content_status") == "pending_protocol_pdf"]
    )
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "partial",
        "total_sections": TOTAL_SECTIONS,
        "loaded_sections": list(LOADED_SECTION_NUMBERS),
        "pending_sections": list(PENDING_SECTION_NUMBERS),
        "loaded_question_count": loaded_question_count,
        "pending_question_count": pending_question_count,
        "pending_reason": (
            "Sections 3-11 await UVDB-QS-003 v11.8 protocol PDF ingest; "
            "section titles marked provisional where not PDF-pinned."
        ),
    }


UVDB_B2_SECTIONS: list[dict[str, Any]] = '''

PENDING_SHELLS = [
    {
        "number": "3",
        "title": "Health and Safety Policy and Leadership",
        "max_score": 0,
        "iso_mapping": {"45001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "4",
        "title": "Risk Assessment and Safe Systems of Work",
        "max_score": 0,
        "iso_mapping": {"45001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "5",
        "title": "Workplace Safety",
        "max_score": 0,
        "iso_mapping": {"45001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "6",
        "title": "Occupational Health",
        "max_score": 0,
        "iso_mapping": {"45001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "7",
        "title": "Competence, Training and Supervision",
        "max_score": 0,
        "iso_mapping": {"45001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "8",
        "title": "Environmental Policy and Compliance",
        "max_score": 0,
        "iso_mapping": {"14001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "9",
        "title": "Environmental Aspects and Impacts",
        "max_score": 0,
        "iso_mapping": {"14001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "10",
        "title": "Waste, Pollution and Resource Management",
        "max_score": 0,
        "iso_mapping": {"14001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
    {
        "number": "11",
        "title": "Sustainability and Corporate Social Responsibility",
        "max_score": 0,
        "iso_mapping": {"14001": "pending"},
        "title_provisional": True,
        "content_status": "pending_protocol_pdf",
        "questions": [],
    },
]


def main() -> None:
    source = (ROOT / "src/api/routes/uvdb.py").read_text()
    tree = ast.parse(source)
    sections_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "UVDB_B2_SECTIONS":
                    sections_node = node.value
                    break

    if sections_node is None:
        raise SystemExit("UVDB_B2_SECTIONS not found")

    loaded = ast.literal_eval(ast.unparse(sections_node))
    loaded_by_num = {s["number"]: s for s in loaded}

    def annotate_loaded(section: dict) -> dict:
        out = dict(section)
        out["title_provisional"] = False
        out["content_status"] = "loaded"
        return out

    all_sections = []
    for i in range(1, 16):
        num = str(i)
        if num in loaded_by_num:
            all_sections.append(annotate_loaded(loaded_by_num[num]))
        else:
            all_sections.append(next(s for s in PENDING_SHELLS if s["number"] == num))

    out_dir = ROOT / "src/domain/uvdb"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "__init__.py").write_text(
        "from src.domain.uvdb.protocol_b2_v118 import (\n"
        "    PROTOCOL_VERSION,\n"
        "    UVDB_B2_SECTIONS,\n"
        "    build_content_coverage,\n"
        ")\n\n"
        '__all__ = ["PROTOCOL_VERSION", "UVDB_B2_SECTIONS", "build_content_coverage"]\n'
    )
    out_path = out_dir / "protocol_b2_v118.py"
    out_path.write_text(HEADER + repr(all_sections) + "\n")
    print(f"Wrote {out_path} ({len(all_sections)} sections)")


if __name__ == "__main__":
    main()
