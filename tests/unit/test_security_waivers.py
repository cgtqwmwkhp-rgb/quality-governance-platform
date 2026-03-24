from datetime import datetime

from scripts.validate_security_waivers import (
    build_pip_audit_ignore_args,
    get_active_waiver_ids,
)


def test_get_active_waiver_ids_filters_expired_entries():
    waivers = {
        "CVE-2026-4539": datetime(2026, 6, 22),
        "CVE-2024-23342": datetime(2026, 4, 4),
        "CVE-2020-0001": datetime(2026, 3, 1),
    }

    active_ids = get_active_waiver_ids(waivers, now=datetime(2026, 3, 24))

    assert active_ids == ["CVE-2024-23342", "CVE-2026-4539"]


def test_build_pip_audit_ignore_args_uses_active_waivers_only():
    waivers = {
        "CVE-2026-4539": datetime(2026, 6, 22),
        "CVE-2020-0001": datetime(2026, 3, 1),
    }

    ignore_args = build_pip_audit_ignore_args(waivers, now=datetime(2026, 3, 24))

    assert ignore_args == ["--ignore-vuln", "CVE-2026-4539"]
