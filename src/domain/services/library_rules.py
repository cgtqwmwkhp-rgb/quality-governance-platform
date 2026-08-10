"""Northern Star Wave W4 / NS-RULE-A — identity rule hard blocks on write.

Loads the authority pack (`northern-star-rules-v6.json` + filename grammar from
`northern-star-v6.json`) and exposes pure validators for the Block-severity
identity rules that must refuse a create/rename rather than warn:

- R01 reference format
- R02 band digit equals cascade level
- R03 function code in the reference equals the function field
- R26 access level required on create
- R32 filename grammar (when a filename already carries a PEL prefix)

R04 / R05 remain enforced by the PostgreSQL immutability trigger and ORM
listeners (NS-1). R06 / R29 remain enforced by the banded allocator (counters
only ever advance; exhausted bands refuse). This module is the single place
the *checkable* identity rules are named so staged hardness (M-08) has one
home — Wave W6+ will add issue-time blocks beside these create-time ones.

Because R26 is the rule that names the access vocabulary, CUT-1 makes this the
one place that vocabulary is defined (``LIBRARY_ACCESS_LEVELS`` +
``normalize_access_level``). F-7 §3 keeps ``documents.access_level`` as the
single live access field and folds the control layer's parallel ``internal``
spelling onto it; the retention half of that converge lives in
``library_retention_policy``.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Final

from src.domain.exceptions import ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RULES_PATH = _REPO_ROOT / "specs" / "governance-library" / "northern-star-rules-v6.json"
_PACK_PATH = _REPO_ROOT / "specs" / "governance-library" / "northern-star-v6.json"

# Wave W4 identity set — hard Block on write. Other R-rules stay warn/queue
# until later waves (WF, nightly, explorer).
RULE_A_IDS: Final[frozenset[str]] = frozenset({"R01", "R02", "R03", "R04", "R05", "R06", "R26", "R29", "R32"})

#: CUT-1 / F-7 §3 — the one Library access vocabulary, least restrictive first.
#: Every module that needs the allowed set imports this rather than re-typing the
#: literals; the control layer's parallel ``internal`` vocabulary folds onto it
#: through :func:`normalize_access_level`.
LIBRARY_ACCESS_LEVELS: Final[tuple[str, ...]] = ("all_staff", "managers", "restricted")

_ALLOWED_ACCESS_LEVELS: Final[frozenset[str]] = frozenset(LIBRARY_ACCESS_LEVELS)

# Control-layer and legacy spellings → the one vocabulary (F-7 §3 "align enum").
# Every alias resolves to a level at least as restrictive as the original, so
# folding the vocabularies can never widen who may read a document:
# ``internal`` / ``public`` are both "everyone inside the tenant" (external
# publication is ``documents.is_public``, a separate field this does not touch),
# and ``confidential`` folds up to ``restricted``.
_ACCESS_LEVEL_ALIASES: Final[dict[str, str]] = {
    "all staff": "all_staff",
    "all_employees": "all_staff",
    "all employees": "all_staff",
    "staff": "all_staff",
    "internal": "all_staff",
    "public": "all_staff",
    "manager": "managers",
    "management": "managers",
    "managers only": "managers",
    "confidential": "restricted",
    "restricted_access": "restricted",
}


@lru_cache(maxsize=1)
def _rules_pack() -> dict:
    return json.loads(_RULES_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _full_pack() -> dict:
    return json.loads(_PACK_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def reference_pattern() -> re.Pattern[str]:
    """R01 — compiled from the authority pack, never a second copy."""
    return re.compile(_rules_pack()["reference_pattern"])


@lru_cache(maxsize=1)
def filename_grammar_pattern() -> re.Pattern[str]:
    """R32 — compiled from northern-star-v6.json `filename_grammar`."""
    return re.compile(_full_pack()["filename_grammar"])


def rule_text(rule_id: str) -> str:
    for row in _rules_pack()["validation_rules"]:
        if row["id"] == rule_id:
            return str(row["rule"])
    raise KeyError(rule_id)


def assert_pel_identity(
    pel_doc_ref: str,
    *,
    function_code: str,
    cascade_level: int,
) -> None:
    """Hard-block R01–R03 for an allocated (or claimed) reference.

    Raises ``ValidationError`` with the rule id in the message so API clients
    and stewards can see which identity rule refused the write.
    """
    ref = (pel_doc_ref or "").strip()
    code = (function_code or "").strip().upper()
    if not reference_pattern().fullmatch(ref):
        raise ValidationError(f"R01: reference {ref!r} does not match " f"{_rules_pack()['reference_pattern']}")

    # PEL-<CODE>-<BAND><SEQ> — band is the first digit after the final '-'
    try:
        prefix, seq = ref.rsplit("-", 1)
        ref_function = prefix.split("-", 1)[1]
        band_digit = int(seq[0])
    except (ValueError, IndexError) as exc:
        raise ValidationError(f"R01: reference {ref!r} could not be parsed") from exc

    if band_digit != int(cascade_level):
        raise ValidationError(
            f"R02: band digit {band_digit} in {ref!r} does not equal " f"cascade_level {cascade_level}"
        )
    if ref_function != code:
        raise ValidationError(f"R03: function {ref_function!r} in {ref!r} does not equal " f"function field {code!r}")


def normalize_access_level(access_level: str | None) -> str | None:
    """Fold any known spelling onto the one Library vocabulary, else ``None``.

    Used at *write* boundaries only — the control layer's create/update path and
    the CUT-1 data migration. Deliberately not used by
    ``document_library_rbac.user_can_read_library_document``: that comparison
    fails closed on an unrecognised value today, and normalising on read would
    turn a value nobody validated into a grant. Converging the vocabulary is a
    write-side decision, not a read-side amnesty.

    Returns ``None`` for a value with no honest mapping, so the caller decides
    whether to refuse or to leave the field alone. It never guesses a level.
    """
    value = (access_level or "").strip().lower()
    if not value:
        return None
    if value in _ALLOWED_ACCESS_LEVELS:
        return value
    return _ACCESS_LEVEL_ALIASES.get(value)


def assert_access_level_required(access_level: str | None) -> str:
    """R26 — every document must carry a concrete access level on create."""
    level = (access_level or "").strip().lower()
    if not level:
        raise ValidationError(
            "R26: access_level is required on create "
            "(default from taxonomy category, or all_staff|managers|restricted)"
        )
    if level not in _ALLOWED_ACCESS_LEVELS:
        raise ValidationError(f"R26: access_level {access_level!r} is not one of " f"{sorted(_ALLOWED_ACCESS_LEVELS)}")
    return level


def assert_filename_grammar_if_pel_prefixed(filename: str | None) -> None:
    """R32 — when a filename already claims a PEL, it must match the grammar.

    Wizard uploads that allocate a fresh PEL often arrive with a working title
    filename; those are not yet PEL-prefixed and are not refused here. Ingest
    of finished files (Northern Star model) *does* use PEL-prefixed names and
    must hard-block on a malformed claim.
    """
    name = (filename or "").strip()
    if not name.upper().startswith("PEL-"):
        return
    # Compare against the basename only — storage paths are not part of R32.
    base = Path(name).name
    if not filename_grammar_pattern().fullmatch(base):
        raise ValidationError(f"R32: filename {base!r} does not match Northern Star filename grammar")
