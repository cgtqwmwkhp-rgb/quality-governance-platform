#!/usr/bin/env python3
"""Check that .env.example covers all Settings class fields.

Compares the keys in .env.example against environment variable names
referenced in the Pydantic Settings class and key configuration files.
"""

import re
import sys
from pathlib import Path


def get_env_example_keys(path: Path) -> set[str]:
    keys = set()
    if not path.exists():
        return keys
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", 1)[0].strip())
    return keys


def get_settings_fields(src_root: Path) -> set[str]:
    fields = set()
    config_files = list(src_root.rglob("config*.py")) + list(src_root.rglob("settings*.py"))
    pattern = re.compile(r"(\w+)\s*[:=].*(?:Field|env=|os\.environ|os\.getenv)")
    env_pattern = re.compile(r'os\.(?:environ|getenv)\[?\(?["\'](\w+)["\']')

    for f in config_files:
        content = f.read_text()
        for match in pattern.finditer(content):
            fields.add(match.group(1).upper())
        for match in env_pattern.finditer(content):
            fields.add(match.group(1))
    return fields


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    env_keys = get_env_example_keys(repo / ".env.example")

    if not env_keys:
        print("[WARN] .env.example is empty or missing")
        return 0

    settings_keys = get_settings_fields(repo / "src")

    missing = settings_keys - env_keys
    if missing:
        print(f"[WARN] {len(missing)} Settings fields not in .env.example:")
        for k in sorted(missing):
            print(f"  - {k}")
    else:
        print("[OK] .env.example covers all detected Settings fields")

    print(f"\n.env.example keys: {len(env_keys)}")
    print(f"Settings fields detected: {len(settings_keys)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
