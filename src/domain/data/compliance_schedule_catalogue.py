"""Pure catalogue loader + idempotent upsert for Compliance Schedule templates.

Safe for Alembic (sync connection) and later async services — no AsyncSession
imports. Mirrors ``document_category_seed_data``: the JSON file is the source of
truth; this module only parses and upserts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, MutableMapping, Optional, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOGUE_JSON_PATH = _REPO_ROOT / "specs" / "compliance-schedule" / "catalogue.json"

EXPECTED_TEMPLATE_COUNT_MIN = 20
EXPECTED_TEMPLATE_COUNT_MAX = 30

_UPSERT_COLUMNS = (
    "template_key",
    "title",
    "taxonomy_id",
    "description",
    "regulatory_basis",
    "frequency_months",
    "frequency_days",
    "anchor",
    "statutory",
    "is_active",
)


def load_catalogue_templates(catalogue_path: Path | None = None) -> list[dict[str, Any]]:
    """Parse catalogue.json into row dicts for ``compliance_requirement_templates``."""
    path = catalogue_path or CATALOGUE_JSON_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    templates = raw.get("templates")
    if not isinstance(templates, list):
        raise ValueError(f"{path} missing 'templates' list")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in templates:
        if not isinstance(item, Mapping):
            raise ValueError("catalogue template entries must be objects")
        key = str(item["template_key"]).strip()
        if not key:
            raise ValueError("template_key must be non-empty")
        if key in seen:
            raise ValueError(f"duplicate template_key: {key}")
        seen.add(key)

        anchor = str(item["anchor"]).strip().lower()
        if anchor not in {"completion", "schedule"}:
            raise ValueError(f"invalid anchor for {key}: {anchor}")

        frequency_months = item.get("frequency_months")
        frequency_days = item.get("frequency_days")
        if frequency_months is None and frequency_days is None:
            raise ValueError(f"{key} needs frequency_months or frequency_days")

        rows.append(
            {
                "template_key": key,
                "title": str(item["title"]).strip(),
                "taxonomy_id": str(item["taxonomy_id"]).strip(),
                "description": (str(item["description"]).strip() if item.get("description") else None),
                "regulatory_basis": (str(item["regulatory_basis"]).strip() if item.get("regulatory_basis") else None),
                "frequency_months": int(frequency_months) if frequency_months is not None else None,
                "frequency_days": int(frequency_days) if frequency_days is not None else None,
                "anchor": anchor,
                "statutory": bool(item.get("statutory", False)),
                "is_active": bool(item.get("is_active", True)),
                "tenant_id": None,
            }
        )
    return rows


def upsert_compliance_templates(
    connection: Any,
    *,
    catalogue_path: Path | None = None,
    table_name: str = "compliance_requirement_templates",
) -> int:
    """Idempotently upsert catalogue rows via ``template_key``.

    ``connection`` is a SQLAlchemy Connection (Alembic ``op.get_bind()``) or any
    object exposing ``execute``. Returns the number of catalogue rows processed.
    """
    import sqlalchemy as sa

    rows = load_catalogue_templates(catalogue_path)
    if not rows:
        return 0

    table = sa.table(
        table_name,
        sa.column("id", sa.Integer),
        sa.column("tenant_id", sa.Integer),
        sa.column("template_key", sa.String),
        sa.column("title", sa.String),
        sa.column("taxonomy_id", sa.String),
        sa.column("description", sa.Text),
        sa.column("regulatory_basis", sa.String),
        sa.column("frequency_months", sa.Integer),
        sa.column("frequency_days", sa.Integer),
        sa.column("anchor", sa.String),
        sa.column("statutory", sa.Boolean),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )

    existing = {
        r.template_key: r.id for r in connection.execute(sa.select(table.c.id, table.c.template_key)).fetchall()
    }

    now = sa.func.now()
    for row in rows:
        payload: MutableMapping[str, Any] = {col: row[col] for col in _UPSERT_COLUMNS}
        payload["tenant_id"] = None
        key = payload["template_key"]
        if key in existing:
            connection.execute(
                table.update()
                .where(table.c.template_key == key)
                .values(**{k: v for k, v in payload.items() if k != "template_key"}, updated_at=now)
            )
        else:
            connection.execute(
                table.insert().values(
                    **payload,
                    created_at=now,
                    updated_at=now,
                )
            )
    return len(rows)


def catalogue_template_keys(catalogue_path: Path | None = None) -> Sequence[str]:
    """Return template keys in catalogue order (for tests)."""
    return [row["template_key"] for row in load_catalogue_templates(catalogue_path)]


__all__ = [
    "CATALOGUE_JSON_PATH",
    "EXPECTED_TEMPLATE_COUNT_MAX",
    "EXPECTED_TEMPLATE_COUNT_MIN",
    "catalogue_template_keys",
    "load_catalogue_templates",
    "upsert_compliance_templates",
]
