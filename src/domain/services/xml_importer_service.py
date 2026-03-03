"""XML Template Importer Service.

Parses Android XML layout files and converts them to audit template structures
compatible with AuditService.create_template(), create_section(), and create_question().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import xml.etree.ElementTree as ET

import defusedxml.ElementTree as SafeET

from src.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)

# Android namespace for attribute lookup
ANDROID_NS = "http://schemas.android.com/apk/res/android"
NS_MAP = {"android": ANDROID_NS}


def _attr(el: ET.Element, name: str, default: str | None = None) -> str | None:
    """Get Android namespaced attribute."""
    val = el.get("{" + ANDROID_NS + "}" + name)
    return val if val is not None else default


def _local_tag(tag: str) -> str:
    """Strip namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


# ---------------------------------------------------------------------------
# Android input type → audit question type mapping
# ---------------------------------------------------------------------------

_EDIT_TEXT_TO_QUESTION_TYPE = {
    "text": "text",
    "textPersonName": "text",
    "textEmailAddress": "text",
    "textPassword": "text",
    "textUri": "text",
    "textCapCharacters": "text",
    "textCapWords": "text",
    "textCapSentences": "text",
    "textAutoComplete": "text",
    "textAutoCorrect": "text",
    "textMultiLine": "textarea",
    "textPostalAddress": "textarea",
    "number": "number",
    "numberSigned": "number",
    "numberDecimal": "number",
    "phone": "text",
    "date": "date",
    "datetime": "datetime",
}


def _edit_text_input_type_to_question_type(input_type: str | None) -> str:
    """Map Android inputType to audit question_type."""
    if not input_type:
        return "text"
    # inputType can be combined with |, e.g. "textMultiLine|textCapSentences"
    first = input_type.split("|")[0].strip()
    return _EDIT_TEXT_TO_QUESTION_TYPE.get(first, "text")


# ---------------------------------------------------------------------------
# Parsed structure (returned by service, passed to AuditService)
# ---------------------------------------------------------------------------


def parse_xml_to_template(
    xml_content: str | bytes,
    *,
    source_filename: str | None = None,
) -> dict[str, Any]:
    """Parse Android XML layout into audit template structure.

    Returns a dict compatible with creating templates via AuditService:
    {
        "name": str,
        "description": str | None,
        "category": str | None,
        "sections": [
            {
                "name": str,  # maps to title
                "order": int,
                "questions": [
                    {
                        "text": str,
                        "question_type": str,
                        "guidance": str | None,
                        "order": int,
                        "options": list | None,  # for select/radio
                        ...
                    }
                ]
            }
        ]
    }
    """
    try:
        root = SafeET.fromstring(xml_content)
    except ET.ParseError as e:
        raise ValidationError(f"Invalid XML: {e}") from e

    # Extract template name from textViewTitle or fallback to filename
    name = _extract_template_name(root, source_filename)
    description = _extract_description(root)

    # Walk the tree and collect sections/questions
    sections = _extract_sections_and_questions(root)

    # Ensure at least one section if we have questions
    if not sections and _has_any_questions(root):
        sections = [
            {
                "name": "General",
                "order": 0,
                "questions": _extract_orphan_questions(root),
            }
        ]
    elif not sections:
        sections = [{"name": "General", "order": 0, "questions": []}]

    return {
        "name": name,
        "description": description,
        "category": _category_from_filename(source_filename),
        "sections": sections,
    }


def _extract_template_name(root: ET.Element, source_filename: str | None) -> str:
    """Get template name from textViewTitle or filename."""
    for el in root.iter():
        if _local_tag(el.tag) == "TextView":
            aid = _attr(el, "id", "")
            if aid and "textViewTitle" in (aid or ""):
                text = _attr(el, "text")
                if text and text.strip():
                    return text.strip()
    if source_filename:
        base = Path(source_filename).stem
        # Convert service_vehicle_health_check -> Vehicle Health Check
        base = base.replace("service_", "").replace("_", " ").title()
        return base
    return "Imported Template"


def _extract_description(root: ET.Element) -> str | None:
    """Extract description from intro LinearLayout text if present."""
    for el in root.iter():
        if _local_tag(el.tag) == "LinearLayout":
            texts = []
            for child in el:
                if _local_tag(child.tag) == "TextView":
                    t = _attr(child, "text")
                    if t and t.strip():
                        texts.append(t.strip())
            if texts:
                return "\n".join(texts[:5])  # First few lines as description
    return None


def _category_from_filename(source_filename: str | None) -> str | None:
    """Infer category from filename (e.g. service_vehicle_* -> 'Vehicle')."""
    if not source_filename:
        return None
    stem = Path(source_filename).stem.lower()
    if "vehicle" in stem or "lcv" in stem or "sprinter" in stem:
        return "Vehicle"
    if "thorough" in stem or "loler" in stem or "exam" in stem:
        return "LOLER"
    if "pat" in stem or "inspection" in stem:
        return "Inspection"
    if "generator" in stem or "gen_" in stem:
        return "Plant & Equipment"
    return "Equipment"


def _has_any_questions(root: ET.Element) -> bool:
    """Check if XML contains any recognizable question widgets."""
    for el in root.iter():
        tag = _local_tag(el.tag)
        if tag in ("EditText", "CheckBox", "RadioGroup", "RadioButton", "Spinner"):
            return True
        if "Spinner" in tag or "AppCompatSpinner" in tag:
            return True
    return False


def _extract_orphan_questions(root: ET.Element) -> list[dict[str, Any]]:
    """Extract questions that don't fall under a clear section."""
    questions = []
    idx = 0
    for el in root.iter():
        tag = _local_tag(el.tag)
        q = _parse_question_element(el, tag, idx)
        if q:
            questions.append(q)
            idx += 1
    return questions


def _extract_sections_and_questions(root: ET.Element) -> list[dict[str, Any]]:
    """Extract sections and questions by walking TableLayout/LinearLayout structure."""
    sections: list[dict[str, Any]] = []
    current_section: dict[str, Any] | None = None
    section_order = 0
    question_order = 0
    seen_header_row = False

    def maybe_start_section(name: str) -> None:
        nonlocal current_section, section_order, question_order
        if current_section and current_section.get("questions"):
            sections.append(current_section)
        current_section = {"name": name, "order": section_order, "questions": []}
        section_order += 1
        question_order = 0

    # Look for TableLayout (common pattern in these XMLs)
    for table in root.iter():
        tag = _local_tag(table.tag)
        if tag != "TableLayout":
            continue

        for row in table:
            row_tag = _local_tag(row.tag)
            if row_tag != "TableRow":
                # Standalone TextView with #DFDFDF = section header
                if row_tag == "TextView":
                    text = _attr(row, "text")
                    bg = _attr(row, "background", "")
                    if text and "#DFDFDF" in (bg or ""):
                        maybe_start_section(text.strip())
                continue

            # TableRow
            question_text = None
            has_radio_group = False
            has_spinner = False
            has_edit_text = False
            edit_hint = None
            input_type = None
            radio_options: list[str] = []

            for cell in row:
                cell_tag = _local_tag(cell.tag)
                if "Spinner" in cell_tag or cell_tag == "Spinner":
                    has_spinner = True
                elif cell_tag == "RadioGroup":
                    has_radio_group = True
                    for rb in cell.iter():
                        if _local_tag(rb.tag) == "RadioButton":
                            # Options often in sibling TextViews
                            pass
                    # RadioGroup with Ok/Adv/Fail/N/A pattern
                    radio_options = ["Ok", "Adv", "Fail", "N/A"]
                elif cell_tag == "EditText":
                    has_edit_text = True
                    edit_hint = _attr(cell, "hint")
                    input_type = _attr(cell, "inputType")
                elif cell_tag == "TextView":
                    text = _attr(cell, "text")
                    bg = _attr(cell, "background", "")
                    if text:
                        if "#DFDFDF" in (bg or "") and not seen_header_row:
                            seen_header_row = True
                            continue  # Header row
                        if question_text is None and not has_radio_group and not has_spinner:
                            question_text = text.strip()

            # Check for nested TableLayout with EditText (comment field)
            for nested in row.iter():
                if _local_tag(nested.tag) == "EditText":
                    has_edit_text = True
                    if edit_hint is None:
                        edit_hint = _attr(nested, "hint")
                    if input_type is None:
                        input_type = _attr(nested, "inputType")
                    break

            # If we have a question (TextView with answer widget)
            if question_text and (has_radio_group or has_spinner or has_edit_text):
                if current_section is None:
                    maybe_start_section("General")

                q_type = "text"
                options = None
                guidance = None

                if has_radio_group:
                    q_type = "pass_fail" if "Ok" in str(radio_options) and "Fail" in str(radio_options) else "radio"
                    options = [{"value": o.lower(), "label": o} for o in radio_options]
                elif has_spinner:
                    q_type = "dropdown"
                    options = [
                        {"value": "option_1", "label": "Option 1"},
                        {"value": "option_2", "label": "Option 2"},
                    ]
                elif has_edit_text:
                    q_type = _edit_text_input_type_to_question_type(input_type)
                    if edit_hint and edit_hint.lower() != "comment":
                        guidance = f"Hint: {edit_hint}"

                current_section["questions"].append(
                    {
                        "text": question_text,
                        "question_type": q_type,
                        "guidance": guidance,
                        "order": question_order,
                        "options": options,
                    }
                )
                question_order += 1

        if current_section and current_section.get("questions"):
            sections.append(current_section)
            current_section = None

    # Also scan LinearLayout groups for section headers + EditText pairs
    for ll in root.iter():
        if _local_tag(ll.tag) != "LinearLayout":
            continue
        section_title = None
        for child in ll:
            ct = _local_tag(child.tag)
            if ct == "TextView":
                t = _attr(child, "text")
                style = _attr(child, "textStyle", "")
                if t and ("bold" in (style or "") or _attr(child, "textSize", "")):
                    section_title = t.strip()
                    break
        if section_title:
            for child in ll:
                if _local_tag(child.tag) == "LinearLayout":
                    for sub in child:
                        st = _local_tag(sub.tag)
                        if st == "TextView" and _attr(sub, "text"):
                            label = _attr(sub, "text", "").strip()
                            if label and label.endswith((":", ")")):
                                # Look for sibling EditText
                                for sib in child:
                                    if _local_tag(sib.tag) == "EditText":
                                        if current_section is None or current_section.get("name") != section_title:
                                            maybe_start_section(section_title)
                                        current_section["questions"].append(
                                            {
                                                "text": label,
                                                "question_type": "text",
                                                "guidance": None,
                                                "order": question_order,
                                                "options": None,
                                            }
                                        )
                                        question_order += 1
                                        break
                        break

    # Handle LinearLayout with bold section header + TableLayout (thorough_mini pattern)
    for ll in root.iter():
        if _local_tag(ll.tag) != "LinearLayout":
            continue
        section_title = None
        for child in ll:
            if _local_tag(child.tag) == "TextView":
                t = _attr(child, "text")
                style = _attr(child, "textStyle", "")
                size = _attr(child, "textSize", "")
                if t and ("bold" in (style or "") or "18sp" in (size or "")):
                    section_title = t.strip()
                    break
        if section_title:
            for tbl in ll.iter():
                if _local_tag(tbl.tag) == "TableLayout":
                    if current_section is None or current_section.get("name") != section_title:
                        maybe_start_section(section_title)
                    question_order = _parse_table_questions(tbl, current_section, question_order)
                    break

    if current_section and current_section.get("questions"):
        sections.append(current_section)

    # Deduplicate and order sections
    seen = set()
    unique_sections = []
    for s in sections:
        key = (
            s["name"],
            tuple((q["text"], q["order"]) for q in s.get("questions", [])),
        )
        if key not in seen:
            seen.add(key)
            unique_sections.append(s)

    return unique_sections if unique_sections else [{"name": "General", "order": 0, "questions": []}]


def _parse_table_questions(tbl: ET.Element, section: dict[str, Any], start_order: int) -> int:
    """Parse questions from a TableLayout within a section."""
    order = start_order
    for row in tbl:
        if _local_tag(row.tag) != "TableRow":
            continue
        question_text = None
        q_type = "text"
        for cell in row:
            ct = _local_tag(cell.tag)
            if ct == "TextView":
                t = _attr(cell, "text")
                if t and t.strip() and question_text is None:
                    question_text = t.strip()
            elif ct == "RadioGroup":
                q_type = "pass_fail"
            elif "Spinner" in ct:
                q_type = "dropdown"
            elif ct == "EditText":
                q_type = "text"
        if question_text:
            section["questions"].append(
                {
                    "text": question_text,
                    "question_type": q_type,
                    "guidance": None,
                    "order": order,
                    "options": None,
                }
            )
            order += 1
    return order


def _parse_question_element(el: ET.Element, tag: str, idx: int) -> dict[str, Any] | None:
    """Parse a single question element (EditText, CheckBox, etc.)."""
    if tag == "EditText":
        hint = _attr(el, "hint")
        input_type = _attr(el, "inputType")
        # Try to get label from preceding TextView - caller context dependent
        return {
            "text": hint or f"Question {idx + 1}",
            "question_type": _edit_text_input_type_to_question_type(input_type),
            "guidance": None,
            "order": idx,
            "options": None,
        }
    if tag == "CheckBox":
        text = _attr(el, "text")
        return {
            "text": text or f"Check item {idx + 1}",
            "question_type": "yes_no",
            "guidance": None,
            "order": idx,
            "options": None,
        }
    if "Spinner" in tag:
        return {
            "text": f"Select item {idx + 1}",
            "question_type": "dropdown",
            "guidance": None,
            "order": idx,
            "options": [{"value": "option_1", "label": "Option 1"}],
        }
    return None


def batch_parse_directory(directory_path: str | Path) -> list[dict[str, Any]]:
    """Parse all XML layout files in a directory and return list of template structures.

    Args:
        directory_path: Absolute or relative path to directory on server.

    Returns:
        List of parsed template dicts, one per valid XML file.
    """
    path = Path(directory_path)
    if not path.is_dir():
        raise ValidationError(f"Not a directory: {directory_path}")

    results = []
    for xml_file in sorted(path.glob("*.xml")):
        try:
            content = xml_file.read_text(encoding="utf-8", errors="replace")
            template = parse_xml_to_template(content, source_filename=xml_file.name)
            results.append(template)
        except Exception as e:
            logger.warning("Failed to parse %s: %s", xml_file.name, e)
    return results


def template_structure_to_audit_payload(template: dict[str, Any]) -> dict[str, Any]:
    """Convert parsed template structure to payload for AuditService.

    Returns the template-level dict for create_template, and sections/questions
    are applied via create_section and create_question.
    """
    return {
        "name": template["name"],
        "description": template.get("description"),
        "category": template.get("category"),
    }


def sections_from_template(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract sections list with questions for create_section/create_question."""
    return template.get("sections", [])
