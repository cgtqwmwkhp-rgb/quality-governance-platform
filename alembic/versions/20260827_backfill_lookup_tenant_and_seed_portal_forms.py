"""Adopt orphaned lookup_options into the tenant, and seed portal form templates.

Two data repairs, both of which are prerequisites for the employee portal
working at all.

1. PX-119 / PX-120 — orphaned lookup options (``tenant_id IS NULL``).
   ``list_lookup_options`` filters ``LookupOption.tenant_id == tenant_id`` and
   every real user carries a non-NULL tenant. ``NULL = 1`` is never true in SQL,
   so any lookup row written without a tenant is unreadable forever. Production
   holds a full set of such rows (workforce_roles, severity_levels,
   emergency_services, medical_assistance, roles, and part of customers): the
   administrator's configuration exists but the application cannot see it. That
   is what made the portal's required ``person_role`` select empty and killed
   the incident journey. This migration adopts those rows into the single
   tenant rather than inserting new values, so nothing is duplicated and no
   configured value is replaced by a guess.

   Collisions are expected — ``customers`` already has rows at both scopes. An
   orphan whose ``(category, code)`` already exists for the tenant is left
   exactly where it is rather than adopted, so the tenant's own row wins.

   The tenant is resolved from the ``tenants`` table, not hardcoded. If there is
   orphaned data and the tenant is ambiguous (more than one row), the migration
   raises instead of guessing which tenant owns the administrator's work.

2. PX-306 — the four portal intake templates return HTTP 404 because no
   migration ever seeded ``form_templates``; the portal silently falls back to
   hard-coded definitions. The templates seeded here mirror those fallbacks
   exactly, published, so the endpoint serves the form users already know.
   ``form_templates.slug`` carries a global UNIQUE index, so a slug can exist
   only once across all tenants; the templates are attached to the
   lowest-numbered tenant (the default organisation).

Both halves are guarded by existence checks and are safe to run repeatedly. The
ids actually changed or inserted are recorded in a ``system_settings`` ledger
row so ``downgrade()`` reverses exactly this migration's effect and nothing an
administrator has done since.

Revision ID: 20260827_lookup_tenant_fix
Revises: 20260826_nm_contract_tenant
Create Date: 2026-08-27
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_lookup_tenant_fix"
down_revision: Union[str, Sequence[str], None] = "20260826_nm_contract_tenant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Key of the system_settings row that records what this migration changed.
SEED_LEDGER_KEY = "migration.20260827_lookup_tenant_fix.applied"

# Source: frontend/src/pages/PortalDynamicForm.tsx ``FALLBACK_TEMPLATES``.
# These are the hard-coded definitions the portal has been falling back to while
# the endpoint 404s, so seeding them keeps the served form identical to the form
# users have actually been filling in.
#
# ``contract`` and ``person_role`` intentionally carry no inline options: the
# renderer injects those from the customers / workforce_roles lookups
# (DynamicFormRenderer.tsx:304-313).
PORTAL_FORM_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "name": "Incident Report",
        "slug": "incident",
        "description": "Report workplace incidents and injuries",
        "form_type": "incident",
        "icon": "AlertTriangle",
        "color": "#ef4444",
        "reference_prefix": "INC",
        "steps": [
            {
                "name": "Customer Details",
                "description": "Which customer does this relate to?",
                "fields": [
                    {
                        "name": "contract",
                        "label": "Select Customer",
                        "field_type": "select",
                        "is_required": True,
                        "width": "full",
                    },
                ],
            },
            {
                "name": "People & Location",
                "description": "Who was involved and where did it happen?",
                "fields": [
                    {
                        "name": "was_involved",
                        "label": "Were you directly involved?",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": [
                            {"value": "yes", "label": "Yes"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    {
                        "name": "person_name",
                        "label": "Full Name",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                        "placeholder": "Enter full name",
                    },
                    {
                        "name": "person_role",
                        "label": "Role",
                        "field_type": "select",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "person_contact",
                        "label": "Contact Number",
                        "field_type": "phone",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "+44...",
                    },
                    {
                        "name": "location",
                        "label": "Location",
                        "field_type": "location",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Where did this occur?",
                    },
                    {
                        "name": "incident_date",
                        "label": "Date",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "incident_time",
                        "label": "Time",
                        "field_type": "time",
                        "is_required": True,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "What Happened",
                "description": "Describe the incident in detail",
                "fields": [
                    {
                        "name": "description",
                        "label": "Description",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "What happened? Be as detailed as possible...",
                        "help_text": "Tip: Use voice input to dictate your description",
                    },
                    {
                        "name": "asset_number",
                        "label": "Asset / Vehicle Registration",
                        "field_type": "text",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "e.g. PN22P102",
                    },
                    {
                        "name": "has_witnesses",
                        "label": "Were there any witnesses?",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": [
                            {"value": "yes", "label": "Yes"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    {
                        "name": "witness_names",
                        "label": "Witness Names",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "Enter witness names and contact details",
                    },
                ],
            },
            {
                "name": "Injuries & Evidence",
                "description": "Document any injuries and upload evidence",
                "fields": [
                    {
                        "name": "has_injuries",
                        "label": "Any injuries sustained?",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": [
                            {"value": "yes", "label": "Yes"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    {
                        "name": "injuries",
                        "label": "Injury Details",
                        "field_type": "body_map",
                        "is_required": False,
                        "width": "full",
                    },
                    {
                        "name": "medical_assistance",
                        "label": "Medical Assistance",
                        "field_type": "select",
                        "is_required": False,
                        "width": "full",
                        "options": [
                            {"value": "none", "label": "No assistance needed"},
                            {"value": "self", "label": "Self application"},
                            {"value": "first-aider", "label": "First aider on site"},
                            {"value": "ambulance", "label": "Ambulance / A&E"},
                            {"value": "gp", "label": "GP / Hospital"},
                        ],
                    },
                    {
                        "name": "photos",
                        "label": "Upload Photos",
                        "field_type": "image",
                        "is_required": False,
                        "width": "full",
                        "help_text": "Upload photos of the scene, injuries, or damage",
                    },
                ],
            },
        ],
    },
    {
        "name": "Near Miss Report",
        "slug": "near-miss",
        "description": "Report close calls and near misses",
        "form_type": "near_miss",
        "icon": "AlertCircle",
        "color": "#f59e0b",
        "reference_prefix": "NM",
        "steps": [
            {
                "name": "Customer Details",
                "description": "Which customer does this relate to?",
                "fields": [
                    {
                        "name": "contract",
                        "label": "Select Customer",
                        "field_type": "select",
                        "is_required": True,
                        "width": "full",
                    },
                ],
            },
            {
                "name": "Location & Time",
                "description": "Where and when did this occur?",
                "fields": [
                    {
                        "name": "location",
                        "label": "Location",
                        "field_type": "location",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "incident_date",
                        "label": "Date",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "incident_time",
                        "label": "Time",
                        "field_type": "time",
                        "is_required": True,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "What Happened",
                "description": "Describe the near miss",
                "fields": [
                    {
                        "name": "description",
                        "label": "Description",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Describe what happened and what could have happened...",
                    },
                    {
                        "name": "potential_consequences",
                        "label": "Potential Consequences",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "What could have happened if this wasn't avoided?",
                    },
                    {
                        "name": "preventive_action",
                        "label": "Suggested Preventive Action",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "How can this be prevented in the future?",
                    },
                    {
                        "name": "photos",
                        "label": "Upload Photos",
                        "field_type": "image",
                        "is_required": False,
                        "width": "full",
                    },
                ],
            },
        ],
    },
    {
        "name": "Customer Complaint",
        "slug": "complaint",
        "description": "Submit customer complaints",
        "form_type": "complaint",
        "icon": "MessageSquare",
        "color": "#3b82f6",
        "reference_prefix": "CMP",
        "steps": [
            {
                "name": "Customer Details",
                "description": "Which customer does this relate to?",
                "fields": [
                    {
                        "name": "contract",
                        "label": "Select Customer",
                        "field_type": "select",
                        "is_required": True,
                        "width": "full",
                    },
                ],
            },
            {
                "name": "Complainant Details",
                "description": "Who raised this complaint?",
                "fields": [
                    {
                        "name": "complainant_name",
                        "label": "Complainant Name",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "complainant_role",
                        "label": "Role / Title",
                        "field_type": "text",
                        "is_required": False,
                        "width": "half",
                    },
                    {
                        "name": "complainant_contact",
                        "label": "Contact Details",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Phone or email",
                    },
                    {
                        "name": "complaint_date",
                        "label": "Date of Complaint",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "location",
                        "label": "Location / Site",
                        "field_type": "text",
                        "is_required": False,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "Complaint Details",
                "description": "Describe the complaint",
                "fields": [
                    {
                        "name": "description",
                        "label": "Complaint Description",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Describe the complaint in detail...",
                    },
                    {
                        "name": "impact",
                        "label": "Impact / Consequences",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "What impact has this had?",
                    },
                    {
                        "name": "resolution_requested",
                        "label": "Resolution Requested",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                        "placeholder": "What resolution is the complainant seeking?",
                    },
                    {
                        "name": "photos",
                        "label": "Supporting Evidence",
                        "field_type": "file",
                        "is_required": False,
                        "width": "full",
                    },
                ],
            },
        ],
    },
    {
        "name": "Road Traffic Collision",
        "slug": "rta",
        "description": "Report a road traffic collision",
        "form_type": "rta",
        "icon": "Car",
        "color": "#9333ea",
        "reference_prefix": "RTA",
        "steps": [
            {
                "name": "Customer Details",
                "description": "Which customer does this relate to?",
                "fields": [
                    {
                        "name": "contract",
                        "label": "Select Customer",
                        "field_type": "select",
                        "is_required": True,
                        "width": "full",
                    },
                ],
            },
            {
                "name": "Collision Details",
                "description": "Where and when did the collision occur?",
                "fields": [
                    {
                        "name": "location",
                        "label": "Location",
                        "field_type": "location",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "incident_date",
                        "label": "Date",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "incident_time",
                        "label": "Time",
                        "field_type": "time",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "vehicle_reg",
                        "label": "Vehicle Registration",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "e.g. AB12 CDE",
                    },
                ],
            },
            {
                "name": "What Happened",
                "description": "Describe the collision",
                "fields": [
                    {
                        "name": "description",
                        "label": "Description",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Describe what happened...",
                    },
                    {
                        "name": "third_party_involved",
                        "label": "Third Party Involved?",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": [
                            {"value": "yes", "label": "Yes"},
                            {"value": "no", "label": "No"},
                        ],
                    },
                    {
                        "name": "photos",
                        "label": "Upload Photos",
                        "field_type": "image",
                        "is_required": False,
                        "width": "full",
                    },
                ],
            },
        ],
    },
)


def _tables() -> dict[str, sa.Table]:
    """Minimal Core table definitions.

    Declared locally rather than imported from ``src.domain.models`` so the
    migration keeps working if the ORM changes later.
    """
    metadata = sa.MetaData()
    tenants = sa.Table(
        "tenants",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
    )
    lookup_options = sa.Table(
        "lookup_options",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("category", sa.String(50)),
        sa.Column("code", sa.String(50)),
        sa.Column("label", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("is_active", sa.Boolean),
        sa.Column("display_order", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    form_templates = sa.Table(
        "form_templates",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("name", sa.String(200)),
        sa.Column("slug", sa.String(100)),
        sa.Column("description", sa.Text),
        sa.Column("form_type", sa.String(50)),
        sa.Column("version", sa.Integer),
        sa.Column("is_active", sa.Boolean),
        sa.Column("is_published", sa.Boolean),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("icon", sa.String(50)),
        sa.Column("color", sa.String(20)),
        sa.Column("allow_drafts", sa.Boolean),
        sa.Column("allow_attachments", sa.Boolean),
        sa.Column("require_signature", sa.Boolean),
        sa.Column("auto_assign_reference", sa.Boolean),
        sa.Column("reference_prefix", sa.String(10)),
        sa.Column("notify_on_submit", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    form_steps = sa.Table(
        "form_steps",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("template_id", sa.Integer),
        sa.Column("name", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("order", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    form_fields = sa.Table(
        "form_fields",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("step_id", sa.Integer),
        sa.Column("name", sa.String(100)),
        sa.Column("label", sa.String(200)),
        sa.Column("field_type", sa.String(50)),
        sa.Column("order", sa.Integer),
        sa.Column("placeholder", sa.String(300)),
        sa.Column("help_text", sa.Text),
        sa.Column("is_required", sa.Boolean),
        sa.Column("options", sa.JSON),
        sa.Column("width", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    system_settings = sa.Table(
        "system_settings",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer),
        sa.Column("key", sa.String(100)),
        sa.Column("value", sa.Text),
        sa.Column("category", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("value_type", sa.String(20)),
        sa.Column("is_public", sa.Boolean),
        sa.Column("is_editable", sa.Boolean),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    return {
        "tenants": tenants,
        "lookup_options": lookup_options,
        "form_templates": form_templates,
        "form_steps": form_steps,
        "form_fields": form_fields,
        "system_settings": system_settings,
    }


_EMPTY_LEDGER: dict[str, list[int]] = {"adopted_lookup_options": [], "form_templates": []}


def _read_ledger(connection: sa.engine.Connection, tables: dict[str, sa.Table]) -> dict[str, list[int]]:
    """Return previously recorded row ids, tolerating a missing/corrupt row."""
    settings_table = tables["system_settings"]
    raw = connection.execute(
        sa.select(settings_table.c.value).where(settings_table.c.key == SEED_LEDGER_KEY)
    ).scalar_one_or_none()
    if not raw:
        return {key: [] for key in _EMPTY_LEDGER}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {key: [] for key in _EMPTY_LEDGER}
    if not isinstance(parsed, dict):
        return {key: [] for key in _EMPTY_LEDGER}
    return {key: [int(i) for i in parsed.get(key, []) if isinstance(i, int)] for key in _EMPTY_LEDGER}


def _write_ledger(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    ledger: dict[str, list[int]],
    now: datetime,
) -> None:
    settings_table = tables["system_settings"]
    payload = json.dumps({key: sorted(set(values)) for key, values in ledger.items()}, sort_keys=True)
    existing = connection.execute(
        sa.select(settings_table.c.id).where(settings_table.c.key == SEED_LEDGER_KEY)
    ).scalar_one_or_none()
    if existing is None:
        connection.execute(
            settings_table.insert().values(
                tenant_id=None,
                key=SEED_LEDGER_KEY,
                value=payload,
                category="migration",
                description=(
                    "Rows adopted or inserted by Alembic revision 20260827_lookup_tenant_fix "
                    "(PX-119, PX-120, PX-306). Used by downgrade() to reverse exactly this "
                    "migration's effect — do not edit."
                ),
                value_type="json",
                is_public=False,
                is_editable=False,
                created_at=now,
                updated_at=now,
            )
        )
    else:
        connection.execute(
            settings_table.update().where(settings_table.c.id == existing).values(value=payload, updated_at=now)
        )


class AmbiguousTenantError(RuntimeError):
    """Raised when orphaned lookup data exists but the owning tenant is unclear."""


def apply_portal_intake_repair(connection: sa.engine.Connection) -> dict[str, Any]:
    """Adopt orphaned lookup options and seed portal templates. Repeat-safe.

    Returns a report of what *this* call changed: per-category adoption counts,
    the orphans skipped because the tenant already has that code, and the
    template ids inserted. A repeat run reports zeroes.
    """
    tables = _tables()
    now = datetime.now(timezone.utc)

    tenant_ids = [
        int(row)
        for row in connection.execute(sa.select(tables["tenants"].c.id).order_by(tables["tenants"].c.id)).scalars()
    ]

    adopted_ids, per_category = _adopt_orphaned_lookup_options(connection, tables, tenant_ids, now)
    template_ids = _seed_form_templates(connection, tables, tenant_ids, now)

    if adopted_ids or template_ids:
        ledger = _read_ledger(connection, tables)
        ledger["adopted_lookup_options"].extend(adopted_ids)
        ledger["form_templates"].extend(template_ids)
        _write_ledger(connection, tables, ledger, now)

    return {
        "adopted_lookup_options": adopted_ids,
        "form_templates": template_ids,
        "per_category": per_category,
    }


def _adopt_orphaned_lookup_options(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    tenant_ids: list[int],
    now: datetime,
) -> tuple[list[int], dict[str, dict[str, int]]]:
    """Move ``tenant_id IS NULL`` lookup options into the tenant that owns them.

    An orphan is skipped when the tenant already has a row with the same
    ``(category, code)``: the tenant's own row is authoritative and adopting the
    orphan would create a duplicate option in every admin and portal dropdown.
    """
    lookup_options = tables["lookup_options"]

    orphans = connection.execute(
        sa.select(lookup_options.c.id, lookup_options.c.category, lookup_options.c.code)
        .where(lookup_options.c.tenant_id.is_(None))
        .order_by(lookup_options.c.category, lookup_options.c.id)
    ).all()
    if not orphans:
        return [], {}

    if len(tenant_ids) != 1:
        raise AmbiguousTenantError(
            f"{len(orphans)} lookup_options rows have tenant_id IS NULL but "
            f"{len(tenant_ids)} tenants exist. Refusing to guess which tenant owns "
            "this configuration — assign these rows manually, then re-run."
        )
    tenant_id = tenant_ids[0]

    taken = {
        (category, code)
        for category, code in connection.execute(
            sa.select(lookup_options.c.category, lookup_options.c.code).where(lookup_options.c.tenant_id == tenant_id)
        ).all()
    }

    adopted: list[int] = []
    per_category: dict[str, dict[str, int]] = {}
    for orphan in orphans:
        stats = per_category.setdefault(orphan.category, {"adopted": 0, "skipped_duplicate": 0})
        if (orphan.category, orphan.code) in taken:
            stats["skipped_duplicate"] += 1
            continue
        connection.execute(
            lookup_options.update().where(lookup_options.c.id == orphan.id).values(tenant_id=tenant_id, updated_at=now)
        )
        taken.add((orphan.category, orphan.code))
        adopted.append(int(orphan.id))
        stats["adopted"] += 1

    return adopted, per_category


def _seed_form_templates(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    tenant_ids: list[int],
    now: datetime,
) -> list[int]:
    """Insert the four portal intake templates, published, for the default tenant."""
    if not tenant_ids:
        return []

    # form_templates.slug is globally unique, so a slug cannot be repeated per
    # tenant. Attach to the lowest-numbered tenant (the default organisation).
    tenant_id = tenant_ids[0]
    form_templates = tables["form_templates"]
    form_steps = tables["form_steps"]
    form_fields = tables["form_fields"]
    inserted: list[int] = []

    for definition in PORTAL_FORM_TEMPLATES:
        already_present = connection.execute(
            sa.select(form_templates.c.id).where(form_templates.c.slug == definition["slug"])
        ).scalar_one_or_none()
        if already_present is not None:
            continue

        template_id = connection.execute(
            form_templates.insert().values(
                tenant_id=tenant_id,
                name=definition["name"],
                slug=definition["slug"],
                description=definition["description"],
                form_type=definition["form_type"],
                version=1,
                is_active=True,
                is_published=True,
                published_at=now,
                icon=definition["icon"],
                color=definition["color"],
                allow_drafts=True,
                allow_attachments=True,
                require_signature=False,
                auto_assign_reference=True,
                reference_prefix=definition["reference_prefix"],
                notify_on_submit=True,
                created_at=now,
                updated_at=now,
            )
        ).inserted_primary_key[0]
        inserted.append(int(template_id))

        for step_order, step in enumerate(definition["steps"]):
            step_id = connection.execute(
                form_steps.insert().values(
                    tenant_id=tenant_id,
                    template_id=template_id,
                    name=step["name"],
                    description=step["description"],
                    order=step_order,
                    created_at=now,
                    updated_at=now,
                )
            ).inserted_primary_key[0]

            for field_order, field in enumerate(step["fields"]):
                connection.execute(
                    form_fields.insert().values(
                        tenant_id=tenant_id,
                        step_id=step_id,
                        name=field["name"],
                        label=field["label"],
                        field_type=field["field_type"],
                        order=field_order,
                        placeholder=field.get("placeholder"),
                        help_text=field.get("help_text"),
                        is_required=field["is_required"],
                        options=field.get("options"),
                        width=field["width"],
                        created_at=now,
                        updated_at=now,
                    )
                )

    return inserted


def revert_portal_intake_repair(connection: sa.engine.Connection) -> dict[str, int]:
    """Reverse exactly what ``apply_portal_intake_repair`` did, then clear the ledger.

    Adopted lookup options are returned to ``tenant_id IS NULL`` rather than
    deleted — the migration never created them, so deleting them would destroy
    the administrator's configuration. Seeded templates are removed, except any
    an administrator has since edited: the API bumps ``version`` on every edit,
    so anything past ``version = 1`` is left alone rather than discarded.
    """
    tables = _tables()
    ledger = _read_ledger(connection, tables)
    reverted = {"adopted_lookup_options": 0, "form_templates": 0}

    if ledger["adopted_lookup_options"]:
        lookup_options = tables["lookup_options"]
        result = connection.execute(
            lookup_options.update()
            .where(
                lookup_options.c.id.in_(ledger["adopted_lookup_options"]),
                lookup_options.c.tenant_id.is_not(None),
            )
            .values(tenant_id=None)
        )
        reverted["adopted_lookup_options"] = result.rowcount or 0

    if ledger["form_templates"]:
        ledger["form_templates"] = [
            int(row)
            for row in connection.execute(
                sa.select(tables["form_templates"].c.id).where(
                    tables["form_templates"].c.id.in_(ledger["form_templates"]),
                    tables["form_templates"].c.version == 1,
                )
            ).scalars()
        ]

    if ledger["form_templates"]:
        # Postgres cascades form_steps / form_fields, but SQLite only honours
        # ON DELETE CASCADE when PRAGMA foreign_keys is on. Delete explicitly.
        step_ids = [
            int(row)
            for row in connection.execute(
                sa.select(tables["form_steps"].c.id).where(
                    tables["form_steps"].c.template_id.in_(ledger["form_templates"])
                )
            ).scalars()
        ]
        if step_ids:
            connection.execute(tables["form_fields"].delete().where(tables["form_fields"].c.step_id.in_(step_ids)))
            connection.execute(tables["form_steps"].delete().where(tables["form_steps"].c.id.in_(step_ids)))
        result = connection.execute(
            tables["form_templates"].delete().where(tables["form_templates"].c.id.in_(ledger["form_templates"]))
        )
        reverted["form_templates"] = result.rowcount or 0

    connection.execute(tables["system_settings"].delete().where(tables["system_settings"].c.key == SEED_LEDGER_KEY))
    return reverted


def upgrade() -> None:
    report = apply_portal_intake_repair(op.get_bind())
    for category, stats in sorted(report["per_category"].items()):
        print(
            f"lookup_options[{category}]: adopted {stats['adopted']}, "
            f"skipped {stats['skipped_duplicate']} (code already present for the tenant)"
        )
    print(
        f"portal intake repair: {len(report['adopted_lookup_options'])} lookup options adopted, "
        f"{len(report['form_templates'])} form templates seeded"
    )


def downgrade() -> None:
    revert_portal_intake_repair(op.get_bind())
