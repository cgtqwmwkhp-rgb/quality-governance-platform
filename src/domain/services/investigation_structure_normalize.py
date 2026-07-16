"""Investigation template/run structure normalization (W2 hard-spine).

Dual-write helpers keep legacy JSON structure/data columns authoritative for the
investigation builder (#1011) while persisting tenant-safe normalized rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import (
    InvestigationRun,
    InvestigationRunFieldResponse,
    InvestigationTemplate,
    InvestigationTemplateField,
    InvestigationTemplateSection,
)

_STRUCTURE_CONFIG_KEYS = frozenset(
    {
        "question_type",
        "allow_na",
        "max_score",
        "max_value",
        "title",
        "description",
        "icon",
        "color",
        "weight",
    }
)
_FIELD_CONFIG_KEYS = frozenset(
    {
        "question_type",
        "allow_na",
        "max_score",
        "max_value",
        "options",
        "conditional_logic",
        "tags",
        "guidance",
        "description",
    }
)


@dataclass(frozen=True)
class ParsedTemplateField:
    section_key: str
    field_key: str
    label: Optional[str]
    field_type: str
    required: bool
    display_order: int
    config_json: Optional[dict]


@dataclass(frozen=True)
class ParsedTemplateSection:
    section_key: str
    title: Optional[str]
    display_order: int
    config_json: Optional[dict]
    fields: Tuple[ParsedTemplateField, ...]


def _section_title(section: dict) -> Optional[str]:
    return section.get("name") or section.get("title")


def _field_type(field: dict) -> str:
    return str(field.get("question_type") or field.get("type") or "text")


def _extract_config(source: dict, allowed_keys: frozenset[str]) -> Optional[dict]:
    config = {key: source[key] for key in allowed_keys if key in source}
    return config or None


def parse_structure_json(structure: Optional[dict]) -> List[ParsedTemplateSection]:
    """Parse legacy template.structure JSON into normalized section/field specs."""
    if not isinstance(structure, dict):
        return []

    sections_out: List[ParsedTemplateSection] = []
    for section_index, section in enumerate(structure.get("sections") or []):
        if not isinstance(section, dict):
            continue

        section_key = str(section.get("id") or f"section_{section_index}")
        parsed_fields: List[ParsedTemplateField] = []
        for field_index, field in enumerate(section.get("fields") or []):
            if not isinstance(field, dict):
                continue
            field_key = str(field.get("id") or f"field_{field_index}")
            parsed_fields.append(
                ParsedTemplateField(
                    section_key=section_key,
                    field_key=field_key,
                    label=field.get("label"),
                    field_type=_field_type(field),
                    required=bool(field.get("required", False)),
                    display_order=field_index,
                    config_json=_extract_config(field, _FIELD_CONFIG_KEYS),
                )
            )

        sections_out.append(
            ParsedTemplateSection(
                section_key=section_key,
                title=_section_title(section),
                display_order=section_index,
                config_json=_extract_config(section, _STRUCTURE_CONFIG_KEYS),
                fields=tuple(parsed_fields),
            )
        )

    return sections_out


def structure_specs_to_json(sections: Iterable[ParsedTemplateSection]) -> Dict[str, Any]:
    """Rebuild legacy structure JSON from parsed specs (dual-read helper)."""
    payload_sections: List[dict] = []
    for section in sections:
        section_payload: dict = {
            "id": section.section_key,
            "name": section.title or section.section_key,
            "fields": [],
        }
        if section.config_json:
            section_payload.update(section.config_json)

        for field in section.fields:
            field_payload: dict = {
                "id": field.field_key,
                "label": field.label or field.field_key,
                "type": field.field_type,
                "question_type": field.field_type,
                "required": field.required,
            }
            if field.config_json:
                field_payload.update(field.config_json)
            section_payload["fields"].append(field_payload)

        payload_sections.append(section_payload)

    return {"sections": payload_sections}


def iter_run_section_values(data: Optional[dict]) -> Iterable[Tuple[str, str, Any]]:
    """Yield (section_key, field_key, value) tuples from legacy run.data JSON."""
    if not isinstance(data, dict):
        return

    nested = data.get("sections")
    if isinstance(nested, dict):
        for section_key, section_data in nested.items():
            if not isinstance(section_data, dict):
                continue
            for field_key, value in section_data.items():
                yield str(section_key), str(field_key), value
        return

    for section_key, section_data in data.items():
        if section_key == "sections" or not isinstance(section_data, dict):
            continue
        for field_key, value in section_data.items():
            yield str(section_key), str(field_key), value


def run_values_to_data_json(
    responses: Iterable[Tuple[str, str, Any]],
    *,
    wrap_sections: bool = True,
) -> Dict[str, Any]:
    """Rebuild legacy run.data JSON from normalized values (dual-read helper)."""
    sections: Dict[str, Dict[str, Any]] = {}
    for section_key, field_key, value in responses:
        sections.setdefault(section_key, {})[field_key] = value

    if wrap_sections:
        return {"sections": sections}
    return sections


def _resolve_tenant_id(template: InvestigationTemplate) -> int:
    if template.tenant_id is None:
        raise ValueError("InvestigationTemplate.tenant_id is required for normalized sync")
    return int(template.tenant_id)


async def sync_template_structure_from_json(
    db: AsyncSession,
    template: InvestigationTemplate,
) -> Tuple[int, int]:
    """Replace normalized template section/field rows from template.structure JSON."""
    tenant_id = _resolve_tenant_id(template)
    specs = parse_structure_json(template.structure if isinstance(template.structure, dict) else {})

    await db.execute(
        delete(InvestigationTemplateSection).where(InvestigationTemplateSection.template_id == template.id)
    )

    section_count = 0
    field_count = 0
    for section_spec in specs:
        section_row = InvestigationTemplateSection(
            tenant_id=tenant_id,
            template_id=template.id,
            section_key=section_spec.section_key,
            title=section_spec.title,
            display_order=section_spec.display_order,
            config_json=section_spec.config_json,
        )
        db.add(section_row)
        await db.flush()
        section_count += 1

        for field_spec in section_spec.fields:
            db.add(
                InvestigationTemplateField(
                    tenant_id=tenant_id,
                    template_id=template.id,
                    section_id=section_row.id,
                    field_key=field_spec.field_key,
                    label=field_spec.label,
                    field_type=field_spec.field_type,
                    required=field_spec.required,
                    display_order=field_spec.display_order,
                    config_json=field_spec.config_json,
                )
            )
            field_count += 1

    return section_count, field_count


async def load_template_field_index(
    db: AsyncSession,
    template_id: int,
) -> Dict[Tuple[str, str], InvestigationTemplateField]:
    """Load template fields keyed by (section_key, field_key)."""
    query = (
        select(InvestigationTemplateField, InvestigationTemplateSection.section_key)
        .join(
            InvestigationTemplateSection,
            InvestigationTemplateField.section_id == InvestigationTemplateSection.id,
        )
        .where(InvestigationTemplateField.template_id == template_id)
        .order_by(
            InvestigationTemplateSection.display_order,
            InvestigationTemplateField.display_order,
        )
    )
    result = await db.execute(query)
    index: Dict[Tuple[str, str], InvestigationTemplateField] = {}
    for field_row, section_key in result.all():
        index[(section_key, field_row.field_key)] = field_row
    return index


async def sync_run_field_responses_from_json(
    db: AsyncSession,
    run: InvestigationRun,
    *,
    template: Optional[InvestigationTemplate] = None,
) -> int:
    """Upsert normalized run field responses from run.data JSON."""
    if template is None:
        template_result = await db.execute(
            select(InvestigationTemplate).where(InvestigationTemplate.id == run.template_id)
        )
        template = template_result.scalar_one_or_none()
    if template is None:
        return 0

    field_index = await load_template_field_index(db, int(template.id))
    if not field_index:
        await sync_template_structure_from_json(db, template)
        field_index = await load_template_field_index(db, int(template.id))

    existing_result = await db.execute(
        select(InvestigationRunFieldResponse).where(InvestigationRunFieldResponse.run_id == run.id)
    )
    existing_by_field_id = {response.template_field_id: response for response in existing_result.scalars().all()}

    seen_field_ids: set[int] = set()
    synced = 0
    for section_key, field_key, value in iter_run_section_values(run.data if isinstance(run.data, dict) else {}):
        template_field = field_index.get((section_key, field_key))
        if template_field is None:
            continue

        seen_field_ids.add(template_field.id)
        existing = existing_by_field_id.get(template_field.id)
        if existing is not None:
            existing.section_key = section_key
            existing.field_key = field_key
            existing.value_json = value
        else:
            db.add(
                InvestigationRunFieldResponse(
                    tenant_id=run.tenant_id,
                    run_id=run.id,
                    template_field_id=template_field.id,
                    section_key=section_key,
                    field_key=field_key,
                    value_json=value,
                )
            )
        synced += 1

    for template_field_id, response in existing_by_field_id.items():
        if template_field_id not in seen_field_ids:
            await db.delete(response)

    return synced


async def build_structure_json_from_rows(
    db: AsyncSession,
    template_id: int,
) -> Dict[str, Any]:
    """Rebuild legacy structure JSON from normalized rows.

    Returns an empty structure when no normalized rows exist. API read paths
    that must distinguish "not migrated" from "canonical empty structure"
    should use :func:`load_canonical_structure_json_from_rows`.
    """
    query = (
        select(InvestigationTemplateSection)
        .where(InvestigationTemplateSection.template_id == template_id)
        .order_by(InvestigationTemplateSection.display_order)
    )
    section_rows = list((await db.execute(query)).scalars().all())
    if not section_rows:
        return {"sections": []}

    field_query = (
        select(InvestigationTemplateField)
        .where(InvestigationTemplateField.template_id == template_id)
        .order_by(InvestigationTemplateField.display_order)
    )
    field_rows = list((await db.execute(field_query)).scalars().all())
    fields_by_section: Dict[int, List[InvestigationTemplateField]] = {}
    for field_row in field_rows:
        fields_by_section.setdefault(field_row.section_id, []).append(field_row)

    specs: List[ParsedTemplateSection] = []
    for section_row in section_rows:
        parsed_fields = tuple(
            ParsedTemplateField(
                section_key=section_row.section_key,
                field_key=field_row.field_key,
                label=field_row.label,
                field_type=field_row.field_type,
                required=field_row.required,
                display_order=field_row.display_order,
                config_json=field_row.config_json,
            )
            for field_row in fields_by_section.get(section_row.id, [])
        )
        specs.append(
            ParsedTemplateSection(
                section_key=section_row.section_key,
                title=section_row.title,
                display_order=section_row.display_order,
                config_json=section_row.config_json,
                fields=parsed_fields,
            )
        )

    return structure_specs_to_json(specs)


async def load_canonical_structure_json_from_rows(
    db: AsyncSession,
    template_id: int,
) -> Optional[Dict[str, Any]]:
    """Return the row-backed canonical structure, or ``None`` before cutover.

    JSON remains the compatible API shape. A template switches to row-backed
    reads only after it has at least one normalized section, allowing existing
    JSON-only records (including intentionally empty structures) to continue
    to read unchanged until their first dual-write.
    """
    has_rows = await db.scalar(
        select(InvestigationTemplateSection.id)
        .where(InvestigationTemplateSection.template_id == template_id)
        .limit(1)
    )
    if has_rows is None:
        return None
    return await build_structure_json_from_rows(db, template_id)


async def build_run_data_json_from_rows(
    db: AsyncSession,
    run_id: int,
    *,
    wrap_sections: bool = True,
) -> Dict[str, Any]:
    """Dual-read helper: rebuild run.data JSON from normalized response rows."""
    query = (
        select(InvestigationRunFieldResponse)
        .where(InvestigationRunFieldResponse.run_id == run_id)
        .order_by(InvestigationRunFieldResponse.section_key, InvestigationRunFieldResponse.field_key)
    )
    responses = (await db.execute(query)).scalars().all()
    tuples = [(row.section_key, row.field_key, row.value_json) for row in responses]
    return run_values_to_data_json(tuples, wrap_sections=wrap_sections)
