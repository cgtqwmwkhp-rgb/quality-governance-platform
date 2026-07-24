"""Safety Insights board-pack export — JSON (serialize_run shape) and PDF."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

ExportFormat = Literal["json", "pdf"]

_TOP_THEMES = 10
_SYNTHESIS_EXCERPT_CHARS = 1200
_RESEARCH_FINDINGS = 6


def _pdf_safe(value: Any, *, max_len: Optional[int] = None) -> str:
    """Helvetica (latin-1) safe text for fpdf2; never invent content on failure."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Drop characters Helvetica cannot encode.
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def _fmt_ratio(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _write_line(pdf: Any, text: str, *, height: float = 5) -> None:
    """Write wrapped text from the left margin (avoids fpdf2 mid-line multi_cell errors)."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, height, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")


class SafetyInsightsExportService:
    """Build board-pack exports from a serialize_run payload (dict input, no DB)."""

    def build_json_board_pack(self, board_pack: dict[str, Any]) -> dict[str, Any]:
        """JSON board pack wrapper matching the existing export response shape."""
        return {"format": "json", "board_pack": board_pack}

    def pdf_filename(self, run_id: Any) -> str:
        return f"safety-insights-run-{run_id}.pdf"

    def build_pdf_bytes(self, board_pack: dict[str, Any]) -> bytes:
        """Render a board-pack PDF from a serialize_run-shaped dict.

        Raises RuntimeError / ModuleNotFoundError on failure (caller maps to HTTP 500).
        """
        try:
            from fpdf import FPDF
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF export unavailable: fpdf2 is not installed in this environment") from exc

        run_id = board_pack.get("id", "unknown")
        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=14)
        pdf.set_margins(left=14, top=14, right=14)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        _write_line(pdf, "Safety Insights Board Pack", height=9)
        pdf.set_font("Helvetica", "", 10)
        _write_line(pdf, f"Generated: {generated_at}", height=6)
        pdf.ln(2)

        self._section_heading(pdf, "Run summary")
        meta_lines = [
            f"Run ID: {run_id}",
            f"Status: {board_pack.get('status')}",
            f"Scope: {board_pack.get('scope')}",
            f"Topic: {board_pack.get('topic_query') or '-'}",
            f"Modules: {', '.join(str(m) for m in (board_pack.get('modules') or [])) or '-'}",
            f"Date from: {board_pack.get('date_from') or '-'}",
            f"Date to: {board_pack.get('date_to') or '-'}",
            f"Created: {board_pack.get('created_at') or '-'}",
            f"Completed: {board_pack.get('completed_at') or '-'}",
            f"Synthesis available: {board_pack.get('synthesis_available')}",
            f"Research available: {board_pack.get('research_available')}",
        ]
        corpus = board_pack.get("corpus_summary") or {}
        if isinstance(corpus, dict) and corpus:
            meta_lines.append(f"Corpus summary: {corpus}")
        for line in meta_lines:
            _write_line(pdf, line)
        pdf.ln(2)

        self._section_heading(pdf, "Top micro-themes")
        themes = board_pack.get("micro_themes") or []
        if not themes:
            _write_line(pdf, "No micro-themes recorded for this run.")
        else:
            for idx, theme in enumerate(themes[:_TOP_THEMES], start=1):
                if not isinstance(theme, dict):
                    continue
                label = theme.get("label") or "Untitled theme"
                case_count = theme.get("case_count")
                share = theme.get("share")
                velocity = theme.get("velocity")
                severity = theme.get("severity_overlay")
                header = (
                    f"{idx}. {label} "
                    f"(n={case_count}, share={share}, velocity={velocity}, severity={severity})"
                )
                pdf.set_font("Helvetica", "B", 10)
                _write_line(pdf, header)
                rationale = theme.get("rationale")
                if rationale:
                    pdf.set_font("Helvetica", "", 9)
                    _write_line(pdf, f"Rationale: {rationale}", height=4.5)
                refs = theme.get("case_refs") or []
                if refs:
                    ref_bits = []
                    for ref in refs[:12]:
                        if isinstance(ref, dict):
                            ref_bits.append(
                                str(ref.get("reference_number") or f"{ref.get('module')}:{ref.get('id')}")
                            )
                        else:
                            ref_bits.append(str(ref))
                    pdf.set_font("Helvetica", "", 8)
                    _write_line(pdf, "Cases: " + ", ".join(ref_bits), height=4)
                pdf.ln(1)
        pdf.ln(1)

        self._section_heading(pdf, "Ratios")
        ratios = board_pack.get("ratios") or {}
        corpus_ratios = (ratios.get("corpus") if isinstance(ratios, dict) else None) or {}
        if not isinstance(corpus_ratios, dict) or not corpus_ratios:
            pdf.set_font("Helvetica", "", 10)
            _write_line(pdf, "No ratio data available.")
        else:
            pdf.set_font("Helvetica", "", 10)
            _write_line(
                pdf,
                "Near-miss to incident: "
                f"{_fmt_ratio(corpus_ratios.get('near_miss_to_incident_ratio'))} "
                f"(NM={corpus_ratios.get('near_misses')}, "
                f"incidents={corpus_ratios.get('incidents')})",
            )
            _write_line(
                pdf,
                "HiPo near-miss to incident: "
                f"{_fmt_ratio(corpus_ratios.get('hipo_near_miss_to_incident_ratio'))} "
                f"(HiPo NM={corpus_ratios.get('hipo_near_misses')})",
            )
            board_years = ratios.get("hs_board_by_year") if isinstance(ratios, dict) else None
            if isinstance(board_years, list) and board_years:
                pdf.set_font("Helvetica", "B", 9)
                _write_line(pdf, "HS board ratios by year")
                pdf.set_font("Helvetica", "", 9)
                for row in board_years[:8]:
                    if not isinstance(row, dict):
                        continue
                    _write_line(
                        pdf,
                        f"Year {row.get('reporting_year')}: "
                        f"NM/injury={_fmt_ratio(row.get('near_miss_to_injury_ratio'))}, "
                        f"HiPo/injury={_fmt_ratio(row.get('hipo_near_miss_to_injury_ratio'))}, "
                        f"LTIFR={_fmt_ratio(row.get('ltifr'))}, AFR={_fmt_ratio(row.get('afr'))}",
                        height=4.5,
                    )
        pdf.ln(2)

        self._section_heading(pdf, "Analyst synthesis (excerpt)")
        synthesis = (board_pack.get("synthesis_text") or "").strip()
        pdf.set_font("Helvetica", "", 10)
        if synthesis:
            _write_line(pdf, _pdf_safe(synthesis, max_len=_SYNTHESIS_EXCERPT_CHARS))
        else:
            _write_line(pdf, "No synthesis text available for this run.")
        pdf.ln(2)

        self._section_heading(pdf, "Research findings")
        findings = board_pack.get("benchmarks") or []
        pdf.set_font("Helvetica", "", 10)
        if not findings:
            _write_line(pdf, "No external research findings recorded.")
        else:
            for idx, finding in enumerate(findings[:_RESEARCH_FINDINGS], start=1):
                if not isinstance(finding, dict):
                    _write_line(pdf, f"{idx}. {finding}")
                    continue
                title = finding.get("title") or "Finding"
                summary = finding.get("summary") or ""
                url = finding.get("source_url") or ""
                pdf.set_font("Helvetica", "B", 10)
                _write_line(pdf, f"{idx}. {title}")
                pdf.set_font("Helvetica", "", 9)
                if summary:
                    _write_line(pdf, summary, height=4.5)
                if url:
                    _write_line(pdf, f"Source: {url}", height=4)
                pdf.ln(1)
        pdf.ln(1)

        self._section_heading(pdf, "Quality scorecard")
        scorecard = board_pack.get("quality_scorecard") or {}
        pdf.set_font("Helvetica", "", 10)
        if not isinstance(scorecard, dict) or not scorecard:
            _write_line(pdf, "No quality scorecard available.")
        else:
            _write_line(pdf, f"Corpus cases scored: {scorecard.get('total', 0)}")
            fields = scorecard.get("fields") or {}
            if isinstance(fields, dict):
                for key, value in fields.items():
                    label = key.replace("_", " ")
                    _write_line(pdf, f"{label}: {_fmt_ratio(value)}")

        try:
            return bytes(pdf.output())
        except Exception as exc:  # noqa: BLE001
            logger.exception("Safety insights PDF render failed for run %s", run_id)
            raise RuntimeError(f"PDF board-pack build failed: {exc}") from exc

    def build_pdf_board_pack(self, board_pack: dict[str, Any]) -> tuple[bytes, str]:
        """Return PDF bytes and Content-Disposition filename."""
        run_id = board_pack.get("id", "unknown")
        return self.build_pdf_bytes(board_pack), self.pdf_filename(run_id)

    @staticmethod
    def _section_heading(pdf: Any, title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        _write_line(pdf, title, height=7)
        pdf.set_font("Helvetica", "", 10)
