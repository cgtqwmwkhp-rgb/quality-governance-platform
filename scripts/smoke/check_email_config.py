#!/usr/bin/env python3
"""Fail closed when EMAIL_ENABLED is set but SMTP credentials are missing.

Does not send mail. Intended for CI / post-deploy smoke.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-readyz",
        default="",
        help="Optional path to a saved /readyz JSON body to validate instead of env.",
    )
    args = parser.parse_args()

    if args.from_readyz:
        with open(args.from_readyz, encoding="utf-8") as fh:
            body = json.load(fh)
        email = body.get("email") or body.get("checks", {}).get("email") or {}
        enabled = bool(email.get("email_enabled"))
        configured = bool(email.get("email_configured"))
        status = email.get("status", "unknown")
    else:
        enabled = _truthy(os.getenv("EMAIL_ENABLED"))
        user = (os.getenv("SMTP_USER") or "").strip()
        password = (os.getenv("SMTP_PASSWORD") or "").strip()
        configured = bool(user and password)
        status = (
            "configured"
            if (enabled and configured)
            else ("misconfigured" if enabled else ("credentials_present" if configured else "not_configured"))
        )

    payload = {
        "ok": not (enabled and not configured),
        "email_enabled": enabled,
        "email_configured": configured,
        "status": status,
    }
    print(json.dumps(payload, indent=2))

    if enabled and not configured:
        print(
            "ERROR: EMAIL_ENABLED is set but SMTP_USER/SMTP_PASSWORD are missing. "
            "Refusing to claim email is ready (no fake send).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
