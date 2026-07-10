"""CI smoke: EMAIL_ENABLED without SMTP must fail closed (Lane 1 / #630)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "smoke" / "check_email_config.py"


def test_check_email_config_passes_when_disabled(monkeypatch):
    env = os.environ.copy()
    env.pop("EMAIL_ENABLED", None)
    env.pop("SMTP_USER", None)
    env.pop("SMTP_PASSWORD", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_check_email_config_fails_when_enabled_without_smtp(monkeypatch):
    env = os.environ.copy()
    env["EMAIL_ENABLED"] = "true"
    env.pop("SMTP_USER", None)
    env.pop("SMTP_PASSWORD", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "SMTP" in proc.stderr
