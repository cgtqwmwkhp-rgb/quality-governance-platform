"""Seed Form Builder templates for three named registers (REG-SSOT-D1).

PEL-HSEQ-5026 (Worker Consultation Record), PEL-HSEQ-5036 (Permit to Work
Record) and PEL-HSEQ-5043 (Remote Working Agreement and Assessment Record) are
named in the PEL-HSEQ-5062 Register of Registers but had no representation in
QGP at all — band ``absent``, no link, nothing an auditor could open. This
revision gives each one a form *definition* on the existing form-config spine
(``form_templates`` / ``form_steps`` / ``form_fields``), the same tables the
four portal intake templates were seeded into by
``20260827_lookup_tenant_fix``. No new table, no new product.

Seeded **unpublished** on purpose. ``POST /api/v1/admin/config/templates/
{id}/publish`` exists to "make it available in the portal", and the portal
intake endpoint only accepts ``incident``, ``complaint``, ``rta`` and
``near_miss`` (``src/api/routes/employee_portal.py``). There is no submission
store for a custom template, so publishing these would advertise a journey that
returns 400. Draft is the true state: the form is defined and editable in the
Form Builder, and an administrator publishes it when a write path exists.

Field names deliberately avoid the lookup-injection heuristics in
``form_publish_validation.resolve_lookup_category`` (anything containing
``role``, ``customer`` or ``contract``), so these templates carry no dependency
on Admin → Lookups and stay publishable on their own terms later.

The ids inserted are recorded in a ``system_settings`` ledger row so
``downgrade()`` reverses exactly this migration's effect. A template an
administrator has since edited (``version`` past 1) is left alone.

Revision ID: 20261116_reg_ssot_d1_forms
Revises: 20261115_aud_notify
Create Date: 2026-11-16
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261116_reg_ssot_d1_forms"
down_revision: Union[str, Sequence[str], None] = "20261115_aud_notify"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Key of the system_settings row that records what this migration inserted.
SEED_LEDGER_KEY = "migration.20261116_reg_ssot_d1_forms.applied"

YES_NO = ({"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"})

# The PEL reference leads the template name so the row found by opening
# PEL-HSEQ-5026 from the Register of Registers is identifiable in the Form
# Builder without a second lookup table mapping templates to doc refs.
REGISTER_FORM_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "doc_ref": "PEL-HSEQ-5026",
        "name": "PEL-HSEQ-5026 Worker Consultation Record",
        "slug": "worker-consultation-record",
        "description": (
            "Record of consultation with non-managerial workers. "
            "ISO 45001 5.4; Health and Safety (Consultation with Employees) Regulations 1996."
        ),
        "form_type": "custom",
        "icon": "Users",
        "color": "#0ea5e9",
        "reference_prefix": "WCR",
        "steps": [
            {
                "name": "Consultation Event",
                "description": "When and how workers were consulted.",
                "fields": [
                    {
                        "name": "event_date",
                        "label": "Date of consultation",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "event_method",
                        "label": "Method",
                        "field_type": "select",
                        "is_required": True,
                        "width": "half",
                        "options": [
                            {"value": "toolbox_talk", "label": "Toolbox talk"},
                            {"value": "safety_committee", "label": "Safety committee"},
                            {"value": "team_briefing", "label": "Team briefing"},
                            {"value": "survey", "label": "Survey"},
                            {"value": "one_to_one", "label": "One to one"},
                        ],
                    },
                    {
                        "name": "site",
                        "label": "Site or depot",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "topic",
                        "label": "Subject consulted on",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "e.g. revised lifting procedure",
                    },
                ],
            },
            {
                "name": "Workers Consulted",
                "description": "Who took part, including any appointed representatives.",
                "fields": [
                    {
                        "name": "participants",
                        "label": "Workers or groups consulted",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "representative",
                        "label": "Employee or safety representative",
                        "field_type": "text",
                        "is_required": False,
                        "width": "full",
                        "help_text": (
                            "HSCE 1996 requires consultation through representatives of "
                            "employee safety where they have been elected."
                        ),
                    },
                ],
            },
            {
                "name": "Matters Raised and Response",
                "description": "What workers raised and what was agreed.",
                "fields": [
                    {
                        "name": "matters_raised",
                        "label": "Matters raised",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "response_given",
                        "label": "Response and actions agreed",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "next_review_date",
                        "label": "Next review date",
                        "field_type": "date",
                        "is_required": False,
                        "width": "half",
                    },
                ],
            },
        ],
    },
    {
        "doc_ref": "PEL-HSEQ-5036",
        "name": "PEL-HSEQ-5036 Permit to Work Record",
        "slug": "permit-to-work-record",
        "description": ("Permit issued, accepted and handed back for hazardous work. " "MHSWR 1999; CDM 2015."),
        "form_type": "custom",
        "icon": "ClipboardCheck",
        "color": "#f59e0b",
        "reference_prefix": "PTW",
        "steps": [
            {
                "name": "Permit Details",
                "description": "What the permit covers and how long it runs.",
                "fields": [
                    {
                        "name": "permit_reference",
                        "label": "Permit reference",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "permit_category",
                        "label": "Permit type",
                        "field_type": "select",
                        "is_required": True,
                        "width": "half",
                        "options": [
                            {"value": "hot_work", "label": "Hot work"},
                            {"value": "confined_space", "label": "Confined space"},
                            {"value": "excavation", "label": "Excavation"},
                            {"value": "work_at_height", "label": "Work at height"},
                            {"value": "electrical_isolation", "label": "Electrical isolation"},
                            {"value": "other", "label": "Other"},
                        ],
                    },
                    {
                        "name": "work_location",
                        "label": "Location",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "valid_from",
                        "label": "Valid from",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "valid_to",
                        "label": "Valid to",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "Work and Precautions",
                "description": "The work authorised and the controls it depends on.",
                "fields": [
                    {
                        "name": "work_description",
                        "label": "Description of work",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "precautions",
                        "label": "Precautions and isolations in place",
                        "field_type": "textarea",
                        "is_required": True,
                        "width": "full",
                    },
                    {
                        "name": "issued_by",
                        "label": "Issued by",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "accepted_by",
                        "label": "Accepted by",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "Handback",
                "description": "Closing the permit. A permit is not complete until it is handed back.",
                "fields": [
                    {
                        "name": "handback_date",
                        "label": "Handback date",
                        "field_type": "date",
                        "is_required": False,
                        "width": "half",
                    },
                    {
                        "name": "handback_by",
                        "label": "Cancelled or handed back by",
                        "field_type": "text",
                        "is_required": False,
                        "width": "half",
                    },
                    {
                        "name": "handback_notes",
                        "label": "Handback notes",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                    },
                ],
            },
        ],
    },
    {
        "doc_ref": "PEL-HSEQ-5043",
        "name": "PEL-HSEQ-5043 Remote Working Agreement and Assessment Record",
        "slug": "remote-working-record",
        "description": (
            "Home or remote workstation agreement and DSE self-assessment. "
            "Health and Safety (Display Screen Equipment) Regulations 1992; MHSWR 1999."
        ),
        "form_type": "custom",
        "icon": "Home",
        "color": "#8b5cf6",
        "reference_prefix": "RWA",
        "steps": [
            {
                "name": "Worker and Arrangement",
                "description": "Who works remotely and from where.",
                "fields": [
                    {
                        "name": "worker_name",
                        "label": "Worker name",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "job_title",
                        "label": "Job title",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "remote_location",
                        "label": "Remote working location",
                        "field_type": "text",
                        "is_required": True,
                        "width": "full",
                        "placeholder": "Home or other remote address",
                    },
                    {
                        "name": "agreement_start",
                        "label": "Arrangement starts",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "days_per_week",
                        "label": "Remote days per week",
                        "field_type": "number",
                        "is_required": False,
                        "width": "half",
                    },
                ],
            },
            {
                "name": "DSE Self-Assessment",
                "description": "Workstation self-assessment under DSE 1992 regulation 2.",
                "fields": [
                    {
                        "name": "workstation_suitable",
                        "label": "Chair, desk and workstation adequate",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": list(YES_NO),
                    },
                    {
                        "name": "screen_and_input",
                        "label": "Screen, keyboard and mouse set up correctly",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": list(YES_NO),
                    },
                    {
                        "name": "environment_suitable",
                        "label": "Lighting, noise and temperature acceptable",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": list(YES_NO),
                    },
                    {
                        "name": "breaks_arranged",
                        "label": "Breaks and changes of activity arranged",
                        "field_type": "toggle",
                        "is_required": True,
                        "width": "full",
                        "options": list(YES_NO),
                    },
                    {
                        "name": "issues_identified",
                        "label": "Issues identified",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                    },
                ],
            },
            {
                "name": "Agreement",
                "description": "What was agreed and when it is reviewed.",
                "fields": [
                    {
                        "name": "actions_agreed",
                        "label": "Actions agreed",
                        "field_type": "textarea",
                        "is_required": False,
                        "width": "full",
                    },
                    {
                        "name": "manager_name",
                        "label": "Manager agreeing the arrangement",
                        "field_type": "text",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "agreement_date",
                        "label": "Date agreed",
                        "field_type": "date",
                        "is_required": True,
                        "width": "half",
                    },
                    {
                        "name": "review_date",
                        "label": "Review date",
                        "field_type": "date",
                        "is_required": False,
                        "width": "half",
                    },
                ],
            },
        ],
    },
)

REGISTER_FORM_SLUGS: tuple[str, ...] = tuple(d["slug"] for d in REGISTER_FORM_TEMPLATES)


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
        "form_templates": form_templates,
        "form_steps": form_steps,
        "form_fields": form_fields,
        "system_settings": system_settings,
    }


def _read_ledger(connection: sa.engine.Connection, tables: dict[str, sa.Table]) -> list[int]:
    """Return previously recorded template ids, tolerating a missing/corrupt row."""
    settings_table = tables["system_settings"]
    raw = connection.execute(
        sa.select(settings_table.c.value).where(settings_table.c.key == SEED_LEDGER_KEY)
    ).scalar_one_or_none()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    return [int(i) for i in parsed.get("form_templates", []) if isinstance(i, int)]


def _write_ledger(
    connection: sa.engine.Connection,
    tables: dict[str, sa.Table],
    template_ids: list[int],
    now: datetime,
) -> None:
    settings_table = tables["system_settings"]
    payload = json.dumps({"form_templates": sorted(set(template_ids))}, sort_keys=True)
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
                    "form_templates rows inserted by Alembic revision 20261116_reg_ssot_d1_forms "
                    "(REG-SSOT-D1). Used by downgrade() to reverse exactly this migration's "
                    "effect — do not edit."
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


def seed_register_form_templates(connection: sa.engine.Connection) -> list[int]:
    """Insert the three register templates as drafts. Repeat-safe.

    Returns the template ids inserted by *this* call; a repeat run returns [].
    """
    tables = _tables()
    now = datetime.now(timezone.utc)

    tenant_ids = [
        int(row)
        for row in connection.execute(sa.select(tables["tenants"].c.id).order_by(tables["tenants"].c.id)).scalars()
    ]
    if not tenant_ids:
        return []

    # form_templates.slug is globally unique, so a slug cannot be repeated per
    # tenant. Attach to the lowest-numbered tenant (the default organisation),
    # matching how the portal intake templates were seeded.
    tenant_id = tenant_ids[0]
    form_templates = tables["form_templates"]
    form_steps = tables["form_steps"]
    form_fields = tables["form_fields"]
    inserted: list[int] = []

    for definition in REGISTER_FORM_TEMPLATES:
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
                # Draft: there is no submission route for a custom template yet.
                is_published=False,
                published_at=None,
                icon=definition["icon"],
                color=definition["color"],
                allow_drafts=True,
                allow_attachments=True,
                require_signature=False,
                auto_assign_reference=True,
                reference_prefix=definition["reference_prefix"],
                notify_on_submit=False,
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

    if inserted:
        ledger = _read_ledger(connection, tables)
        ledger.extend(inserted)
        _write_ledger(connection, tables, ledger, now)

    return inserted


def revert_register_form_templates(connection: sa.engine.Connection) -> int:
    """Delete only the templates this migration inserted, then clear the ledger.

    A template an administrator has edited is left in place: the API bumps
    ``version`` on every edit, so anything past ``version = 1`` is somebody's
    work rather than this migration's output.
    """
    tables = _tables()
    ledger = _read_ledger(connection, tables)
    removed = 0

    if ledger:
        deletable = [
            int(row)
            for row in connection.execute(
                sa.select(tables["form_templates"].c.id).where(
                    tables["form_templates"].c.id.in_(ledger),
                    tables["form_templates"].c.version == 1,
                )
            ).scalars()
        ]

        if deletable:
            # Postgres cascades form_steps / form_fields, but SQLite only honours
            # ON DELETE CASCADE when PRAGMA foreign_keys is on. Delete explicitly.
            step_ids = [
                int(row)
                for row in connection.execute(
                    sa.select(tables["form_steps"].c.id).where(tables["form_steps"].c.template_id.in_(deletable))
                ).scalars()
            ]
            if step_ids:
                connection.execute(tables["form_fields"].delete().where(tables["form_fields"].c.step_id.in_(step_ids)))
                connection.execute(tables["form_steps"].delete().where(tables["form_steps"].c.id.in_(step_ids)))
            result = connection.execute(
                tables["form_templates"].delete().where(tables["form_templates"].c.id.in_(deletable))
            )
            removed = result.rowcount or 0

    connection.execute(tables["system_settings"].delete().where(tables["system_settings"].c.key == SEED_LEDGER_KEY))
    return removed


def upgrade() -> None:
    inserted = seed_register_form_templates(op.get_bind())
    print(f"REG-SSOT-D1: {len(inserted)} register form templates seeded as drafts")


def downgrade() -> None:
    revert_register_form_templates(op.get_bind())
