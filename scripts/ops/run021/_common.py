"""Shared safety helpers for Run021 ops-park scripts.

Hard rules:
- Dry-run is the default. ``--apply`` is opt-in.
- Prod-looking environments refuse ``--apply`` unless ``--i-understand-prod``.
- Never invent an ``--admin`` shortcut; operators use the runbook.
- These scripts are NOT wired into CI deploy / conveyor write paths.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

# Title / name / email fragments that mark UAT / CUJ / smoke debris (case-insensitive).
TEST_TOKEN_RE = re.compile(
    r"(?:"
    r"\bUAT\b|"
    r"\bCUJ\b|"
    r"\bTEST\b|"
    r"\bsmoke\b|"
    r"\bFIXUP\b|"
    r"\bRBAC\b|"
    r"\bPlaywright\b|"
    r"good title here|"
    r"portal INC|"
    r"sev bogus|"
    r"API probe"
    r")",
    re.IGNORECASE,
)

# Portal hex refs: PREFIX-YYYY-XXXXXXXX (8 hex) vs sequential PREFIX-YYYY-####.
HEX_REF_RE = re.compile(r"^(INC|COMP|RTA|NM)-(\d{4})-([0-9A-F]{8})$")
SEQ_REF_RE = re.compile(r"^(INC|COMP|RTA|NM)-(\d{4})-(\d{4,})$")

PORTAL_TEMPLATE_SLUGS: tuple[str, ...] = ("incident", "near-miss", "complaint", "rta")

PROD_ENV_MARKERS = frozenset(
    {
        "production",
        "prod",
        "live",
    }
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def looks_like_prod(env: Optional[str] = None) -> bool:
    """Return True when APP_ENV / ENVIRONMENT / QGP_ENV looks production-like."""
    raw = (env or os.environ.get("APP_ENV") or os.environ.get("ENVIRONMENT") or os.environ.get("QGP_ENV") or "").strip()
    return raw.lower() in PROD_ENV_MARKERS


def add_safety_args(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the standard dry-run / apply / prod-ack flags."""
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute mutations. Default is dry-run (report only). Requires human approval per runbook.",
    )
    parser.add_argument(
        "--i-understand-prod",
        action="store_true",
        default=False,
        dest="i_understand_prod",
        help="Required together with --apply when APP_ENV/ENVIRONMENT looks like production.",
    )
    parser.add_argument(
        "--tenant-id",
        type=int,
        default=None,
        help="Optional tenant filter. When omitted, scripts report across all tenants (still dry-run by default).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Emit machine-readable JSON summary on stdout (human lines still go to stderr).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max sample rows to print per bucket (default 200).",
    )
    return parser


def enforce_apply_safety(*, apply: bool, i_understand_prod: bool) -> str:
    """Return mode label; abort if apply is requested unsafely against prod."""
    if not apply:
        return "dry-run"
    if looks_like_prod() and not i_understand_prod:
        print(
            "REFUSING --apply: environment looks like production "
            f"(APP_ENV={os.environ.get('APP_ENV')!r} ENVIRONMENT={os.environ.get('ENVIRONMENT')!r}).\n"
            "Human approval is required. Re-run with --apply --i-understand-prod only after "
            "the Run021 ops-park runbook sign-off is complete.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if looks_like_prod():
        print(
            "WARNING: --apply on a production-like environment. "
            "Proceeding only because --i-understand-prod was set. "
            "Ensure a named human approved this run.",
            file=sys.stderr,
        )
        return "apply-prod"
    return "apply"


def matches_test_token(*parts: Optional[str]) -> bool:
    blob = " ".join(p for p in parts if p)
    return bool(blob and TEST_TOKEN_RE.search(blob))


def is_hex_reference(ref: Optional[str]) -> bool:
    return bool(ref and HEX_REF_RE.match(ref.strip()))


def is_sequential_reference(ref: Optional[str]) -> bool:
    return bool(ref and SEQ_REF_RE.match(ref.strip()) and not is_hex_reference(ref))


def emit_report(payload: dict[str, Any], *, as_json: bool) -> None:
    payload = {**payload, "generated_at": utc_now_iso()}
    if as_json:
        print(json.dumps(payload, indent=2, default=_json_default))
        return
    mode = payload.get("mode", "?")
    print(f"mode={mode}")
    for key, value in payload.items():
        if key in {"mode", "generated_at", "script"}:
            continue
        if isinstance(value, list) and value and isinstance(value[0], dict):
            print(f"\n## {key} ({len(value)})")
            for row in value[:50]:
                print(" -", _fmt_row(row))
            if len(value) > 50:
                print(f"   … {len(value) - 50} more")
        elif isinstance(value, dict):
            print(f"\n## {key}")
            for k, v in value.items():
                print(f"  {k}: {v}")
        else:
            print(f"{key}: {value}")


def _fmt_row(row: dict[str, Any]) -> str:
    preferred = ("px", "table", "id", "reference_number", "title", "name", "email", "slug", "status", "reason")
    bits = []
    for key in preferred:
        if key in row and row[key] is not None:
            bits.append(f"{key}={row[key]!r}")
    for key, value in row.items():
        if key in preferred:
            continue
        bits.append(f"{key}={value!r}")
    return " ".join(bits)


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def truncate(rows: Sequence[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return list(rows[: max(0, limit)])


def require_database_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI")
    if not url:
        print(
            "DATABASE_URL (or SQLALCHEMY_DATABASE_URI) is required to connect. "
            "Dry-run inventory still needs a read-only connection; no writes occur without --apply.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return url


async def open_session():
    """Lazy-import the app session maker so `--help` works without a DB."""
    from src.infrastructure.database import async_session_maker

    return async_session_maker()


def summarise_counts(rows: Iterable[dict[str, Any]], key: str = "px") -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        bucket = str(row.get(key) or "unknown")
        out[bucket] = out.get(bucket, 0) + 1
    return out
