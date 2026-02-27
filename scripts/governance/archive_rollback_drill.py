#!/usr/bin/env python3
"""Archive rollback drill evidence with timestamped output."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive rollback drill report")
    parser.add_argument("--release-sha", required=True)
    parser.add_argument("--rollback-sha", required=True)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--recovery-minutes", required=True, type=int)
    parser.add_argument("--notes", default="")
    parser.add_argument("--output-dir", default="docs/evidence")
    args = parser.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"ROLLBACK_DRILL_{ts}.md"

    content = f"""# Rollback Drill Evidence

- Timestamp (UTC): {ts}
- Operator: {args.operator}
- Release SHA: {args.release_sha}
- Rollback SHA: {args.rollback_sha}
- Recovery time (minutes): {args.recovery_minutes}
- Result: {"PASS" if args.recovery_minutes <= 15 else "FAIL"}
- Notes: {args.notes or "None"}
"""
    output_file.write_text(content, encoding="utf-8")
    print(f"Wrote rollback drill evidence: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
