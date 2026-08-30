"""Seed the PEL-HSEQ-5052 Waste Duty of Care record form (REG-SSOT-D2).

PEL-HSEQ-5052 is named in the PEL-HSEQ-5062 Register of Registers and covers
every controlled-waste movement (EPA 1990 s.34; transfer-note contents per the
Waste (England and Wales) Regulations 2011 reg 35). In QGP it was catalogue
band ``document`` with no link at all — an auditor could read that the register
exists and had nowhere to open.

This revision gives it a form *definition* on the existing form-config spine
(``form_templates`` / ``form_steps`` / ``form_fields``), exactly as
``20261116_reg_ssot_d1_forms`` did for PEL-HSEQ-5026 / 5036 / 5043. No new
table, no waste-consignment schema, no second product.

**Where the evidence lives.** The signed transfer or consignment note is a
file, and QGP already has exactly one place for files: the Governance Library
(``documents``), reached by ``POST /api/v1/documents/upload`` with a
``function_code`` and ``cascade_level``, which allocates the immutable
``PEL-<FUNCTION>-<BAND><SEQ>`` reference through
``document_category_service.allocate_pel_doc_ref``. So this record does **not**
carry the note: it carries a *pointer* to it. The final step captures the
filed document's ``pel_doc_ref`` in a text field whose ``pattern`` is the
Northern Star reference pattern, and ``allow_attachments`` is **off** so nobody
can grow a second blob library behind this register by re-uploading the note
here. A pointer that turns out to be wrong is visibly wrong; a duplicate blob
is silently wrong.

Seeded **unpublished**, for the same reason D1 was: the portal intake endpoint
only accepts ``incident``, ``complaint``, ``rta`` and ``near_miss``
(``src/api/routes/employee_portal.py``) and there is no submission store for a
custom template, so publishing this would advertise a journey that returns 400.
Draft is the true state — the form is defined and editable in the Form Builder,
and an administrator publishes it when a write path exists.

Field names deliberately avoid the lookup-injection heuristics in
``form_publish_validation.resolve_lookup_category`` (any ``select`` whose name
contains ``role``, ``customer`` or ``contract``), so this template carries no
dependency on Admin → Lookups and stays publishable on its own terms later.
Note this rules out ``contractor_*`` on a select — ``contract`` is a substring.

The ids inserted are recorded in a ``system_settings`` ledger row so
``downgrade()`` reverses exactly this migration's effect. A template an
administrator has since edited (``version`` past 1) is left alone.

Revision ID: 20261117_reg_ssot_d2_waste
Revises: 20261116_reg_ssot_d1_forms
Create Date: 2026-11-17
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261117_reg_ssot_d2_waste"
down_revision: Union[str, Sequence[str], None] = "20261116_reg_ssot_d1_forms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Key of the system_settings row that records what this migration inserted.
SEED_LEDGER_KEY = "migration.20261117_reg_ssot_d2_waste.applied"

YES_NO = ({"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"})

# Literal copy of ``reference_pattern`` in
# specs/governance-library/northern-star-rules-v6.json, which is what
# ``allocate_pel_doc_ref`` issues and ``library_rules.assert_pel_identity``
# enforces. Copied rather than read from the spec because a migration has to
# keep producing the same rows forever; a test asserts the two still agree, so
# a spec change surfaces as a decision rather than as drift.
PEL_DOC_REF_PATTERN = "^PEL-(HSEQ|IT|FAC|PPL|PROC|FLT|CTR|SVC|TECH|DP|FIN|COM)-[1-5][0-9]{3}$"

# European Waste Catalogue / List of Waste code: three pairs of digits, with a
# trailing asterisk for absolute or mirror hazardous entries (e.g. "17 05 03*").
EWC_CODE_PATTERN = r"^\d{2}\s?\d{2}\s?\d{2}\*?$"

# The PEL reference leads the template name so the row found by opening
# PEL-HSEQ-5052 from the Register of Registers is identifiable in the Form
# Builder without a second lookup table mapping templates to doc refs.
WASTE_REGISTER_TEMPLATE: dict[str, Any] = {
    "doc_ref": "PEL-HSEQ-5052",
    "name": "PEL-HSEQ-5052 Waste Duty of Care Record",
    "slug": "waste-duty-of-care-record",
    "description": (
        "One controlled-waste movement: what moved, who handled it, and the "
        "Governance Library reference of the filed transfer or consignment "
        "note. EPA 1990 s.34; Waste (England and Wales) Regulations 2011 reg 35."
    ),
    "form_type": "custom",
    "icon": "Trash2",
    "color": "#16a34a",
    "reference_prefix": "WDC",
    # The note itself is filed to the Governance Library and referenced by
    # pel_doc_ref. Attachments here would be a second, ungoverned copy.
    "allow_attachments": False,
    "steps": [
        {
            "name": "Waste Movement",
            "description": "What moved, when, and from where.",
            "fields": [
                {
                    "name": "transfer_date",
                    "label": "Date of transfer",
                    "field_type": "date",
                    "is_required": True,
                    "width": "half",
                },
                {
                    "name": "transfer_direction",
                    "label": "Direction",
                    "field_type": "select",
                    "is_required": True,
                    "width": "half",
                    "options": [
                        {"value": "removed_from_site", "label": "Waste removed from a Plantexpand site"},
                        {"value": "received_on_site", "label": "Waste received onto a Plantexpand site"},
                    ],
                },
                {
                    "name": "origin_site",
                    "label": "Site or premises the waste came from",
                    "field_type": "text",
                    "is_required": True,
                    "width": "full",
                },
                {
                    "name": "ewc_code",
                    "label": "EWC / List of Waste code",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "pattern": EWC_CODE_PATTERN,
                    "placeholder": "17 05 04",
                    "help_text": "Six digits. Add a trailing * for a hazardous entry, e.g. 17 05 03*.",
                },
                {
                    "name": "is_hazardous",
                    "label": "Hazardous waste",
                    "field_type": "toggle",
                    "is_required": True,
                    "width": "half",
                    "options": list(YES_NO),
                    "help_text": (
                        "Hazardous movements need a consignment note under the Hazardous Waste "
                        "Regulations 2005, not a transfer note."
                    ),
                },
                {
                    "name": "waste_description",
                    "label": "Description of the waste",
                    "field_type": "textarea",
                    "is_required": True,
                    "width": "full",
                    "help_text": "Reg 35 requires a description good enough for the next holder to handle it lawfully.",
                },
                {
                    "name": "quantity_description",
                    "label": "Quantity",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "placeholder": "2 skips, approx 3 tonnes",
                },
                {
                    "name": "containment_type",
                    "label": "How the waste was contained",
                    "field_type": "select",
                    "is_required": True,
                    "width": "half",
                    "options": [
                        {"value": "skip", "label": "Skip"},
                        {"value": "bulk_tipper", "label": "Bulk tipper"},
                        {"value": "drum", "label": "Drum"},
                        {"value": "ibc", "label": "IBC"},
                        {"value": "wheeled_bin", "label": "Wheeled bin"},
                        {"value": "loose_load", "label": "Loose load"},
                        {"value": "other", "label": "Other"},
                    ],
                },
            ],
        },
        {
            "name": "Transfer Parties",
            "description": "Who handed the waste over and who took it, with their authorisations.",
            "fields": [
                {
                    "name": "transferor_name",
                    "label": "Transferor (who handed the waste over)",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                },
                {
                    "name": "transferor_sic_code",
                    "label": "Transferor SIC 2007 code",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "pattern": r"^\d{5}$",
                    "placeholder": "43120",
                    "help_text": "Reg 35(2) requires the transferor's SIC code on the transfer note.",
                },
                {
                    "name": "transferee_name",
                    "label": "Transferee (carrier, broker or dealer)",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                },
                {
                    "name": "carrier_registration_number",
                    "label": "Waste carrier registration number",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "placeholder": "CBDU123456",
                    "help_text": (
                        "s.34(1)(c): transfer only to an authorised person. Registration formats "
                        "differ between the four UK regulators, so this is not format-checked — "
                        "record it as it appears on the carrier's certificate."
                    ),
                },
                {
                    "name": "destination_site",
                    "label": "Receiving site",
                    "field_type": "text",
                    "is_required": True,
                    "width": "full",
                },
                {
                    "name": "destination_permit_reference",
                    "label": "Receiving site permit or exemption number",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                },
            ],
        },
        {
            "name": "Filed Transfer Note",
            "description": "The note itself lives in the Governance Library. This step records where, not a copy.",
            "fields": [
                {
                    "name": "transfer_note_reference",
                    "label": "Transfer or consignment note number",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "help_text": "The number printed on the carrier's note, not a QGP reference.",
                },
                {
                    "name": "transfer_note_pel_doc_ref",
                    "label": "Filed note, Governance Library reference",
                    "field_type": "text",
                    "is_required": True,
                    "width": "half",
                    "pattern": PEL_DOC_REF_PATTERN,
                    "placeholder": "PEL-HSEQ-5001",
                    "help_text": (
                        "Upload the signed note to the Library first (Documents → Upload, "
                        "function HSEQ, cascade level 5). The Library issues the PEL reference; "
                        "paste it here. Do not attach a second copy to this record."
                    ),
                },
                {
                    "name": "retain_until",
                    "label": "Retain until",
                    "field_type": "date",
                    "is_required": False,
                    "width": "half",
                    "help_text": (
                        "Statutory minimum is two years for a transfer note and three for a "
                        "hazardous waste consignment note."
                    ),
                },
                {
                    "name": "duty_of_care_notes",
                    "label": "Duty of care notes",
                    "field_type": "textarea",
                    "is_required": False,
                    "width": "full",
                    "placeholder": "Checks made on the carrier or receiving site, and anything that went wrong.",
                },
            ],
        },
    ],
}

REGISTER_FORM_TEMPLATES: tuple[dict[str, Any], ...] = (WASTE_REGISTER_TEMPLATE,)

REGISTER_FORM_SLUGS: tuple[str, ...] = tuple(d["slug"] for d in REGISTER_FORM_TEMPLATES)


def _tables() -> dict[str, sa.Table]:
    """Minimal Core table definitions.

    Declared locally rather than imported from ``src.domain.models`` so the
    migration keeps working if the ORM changes later. ``form_fields.pattern``
    is carried here because D2's pointer field depends on it; the D1 revision
    did not need it.
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
        sa.Column("pattern", sa.String(500)),
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
                    "form_templates rows inserted by Alembic revision 20261117_reg_ssot_d2_waste "
                    "(REG-SSOT-D2). Used by downgrade() to reverse exactly this migration's "
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


def seed_waste_duty_of_care_form(connection: sa.engine.Connection) -> list[int]:
    """Insert the PEL-HSEQ-5052 template as a draft. Repeat-safe.

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
    # matching how the D1 register templates were seeded.
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
                allow_attachments=definition["allow_attachments"],
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
                        pattern=field.get("pattern"),
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


def revert_waste_duty_of_care_form(connection: sa.engine.Connection) -> int:
    """Delete only the template this migration inserted, then clear the ledger.

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
    inserted = seed_waste_duty_of_care_form(op.get_bind())
    print(f"REG-SSOT-D2: {len(inserted)} waste duty of care form template seeded as a draft")


def downgrade() -> None:
    revert_waste_duty_of_care_form(op.get_bind())
