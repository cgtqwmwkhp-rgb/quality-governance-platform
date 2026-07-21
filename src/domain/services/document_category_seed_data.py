"""Static seed data for the Governance Library taxonomy (Wave W0).

Single source of truth for both the Alembic migration
(``alembic/versions/20260719_gov_lib_w0_taxonomy_pel.py``) and the
app-level idempotent reseed path
(``src.domain.services.document_category_service``), so the 86-category
taxonomy and the tag vocabulary are defined exactly once. Pure data/parsing
only — no ORM/session imports, so it is safe for both the sync migration
context and the async service context to import.

See ``specs/governance-library/README.md`` for the decisions this data
encodes (06.04 deactivated; ISO standards tags dropped).
"""

import json
from pathlib import Path
from typing import Any, TypedDict

# Level-2 taxonomy_id values that must always seed inactive.
# 06.04 = "O-Licence & Tachograph" (HGV operator-licence compliance) —
# Plantexpand does not currently run HGVs under an O-licence.
DEACTIVATED_TAXONOMY_IDS = frozenset({"06.04"})

_REPO_ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_JSON_PATH = _REPO_ROOT / "specs" / "governance-library" / "taxonomy.json"

EXPECTED_CATEGORY_COUNT = 86


class TagSeedRow(TypedDict):
    slug: str
    label: str
    group: str


# Controlled tag vocabulary (governance-library SPEC.md §10), minus
# iso-9001 / iso-14001 / iso-45001 / iso-27001 per the Wave W0 decision to
# drop ISO certification tags from the required seed. `planet-mark` and all
# subject/audience/process tags are kept unchanged.
TAG_SEED: list[TagSeedRow] = [
    {"slug": "planet-mark", "label": "Planet Mark", "group": "standards"},
    {"slug": "fire", "label": "Fire", "group": "subjects"},
    {"slug": "electrical", "label": "Electrical", "group": "subjects"},
    {"slug": "pat", "label": "PAT Testing", "group": "subjects"},
    {"slug": "ev-high-voltage", "label": "EV High Voltage", "group": "subjects"},
    {"slug": "lifting", "label": "Lifting", "group": "subjects"},
    {"slug": "pressure-systems", "label": "Pressure Systems", "group": "subjects"},
    {"slug": "asbestos", "label": "Asbestos", "group": "subjects"},
    {"slug": "legionella", "label": "Legionella", "group": "subjects"},
    {"slug": "coshh", "label": "COSHH", "group": "subjects"},
    {"slug": "havs", "label": "HAVS", "group": "subjects"},
    {"slug": "dse", "label": "DSE", "group": "subjects"},
    {"slug": "buildings", "label": "Buildings", "group": "subjects"},
    {"slug": "driving", "label": "Driving", "group": "subjects"},
    {"slug": "waste", "label": "Waste", "group": "subjects"},
    {"slug": "gdpr", "label": "GDPR", "group": "subjects"},
    {"slug": "building-safety-act", "label": "Building Safety Act", "group": "subjects"},
    {"slug": "mobile-engineers", "label": "Mobile Engineers", "group": "audience"},
    {"slug": "workshop", "label": "Workshop", "group": "audience"},
    {"slug": "office", "label": "Office", "group": "audience"},
    {"slug": "drivers", "label": "Drivers", "group": "audience"},
    {"slug": "managers-only-content", "label": "Managers Only Content", "group": "audience"},
    {"slug": "audit-evidence", "label": "Audit Evidence", "group": "process"},
    {"slug": "client-required", "label": "Client Required", "group": "process"},
    {"slug": "induction-pack", "label": "Induction Pack", "group": "process"},
]


def load_taxonomy_categories(taxonomy_path: Path | None = None) -> list[dict[str, Any]]:
    """Parse taxonomy.json into row dicts keyed to `DocumentCategory` columns.

    Each row's `taxonomy_id` is the taxonomy.json `id` field (e.g. "01",
    "04.04"); `active` is forced False for `DEACTIVATED_TAXONOMY_IDS`
    regardless of what taxonomy.json says, so re-seeding never silently
    reactivates a category the business has deliberately retired.
    """
    path = taxonomy_path or TAXONOMY_JSON_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for cat in raw["categories"]:
        taxonomy_id = cat["id"]
        rows.append(
            {
                "taxonomy_id": taxonomy_id,
                "parent_taxonomy_id": cat.get("parent_id"),
                "level": cat["level"],
                "sort_order": cat["sort_order"],
                "name": cat["name"],
                "slug": cat["slug"],
                "ref_prefix": cat["ref_prefix"],
                "description": cat.get("description"),
                "default_access": cat.get("default_access"),
                "access_note": cat.get("access_note"),
                "suggested_owner_role": cat.get("suggested_owner_role"),
                "review_cycle": cat.get("review_cycle"),
                "retention_rule": cat.get("retention_rule"),
                "typical_contents": cat.get("typical_contents"),
                "active": taxonomy_id not in DEACTIVATED_TAXONOMY_IDS,
            }
        )
    return rows
