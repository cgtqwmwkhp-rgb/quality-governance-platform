"""Guard: google-genai constraint and call sites stay on the 2.x SDK surface."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_requirements_floor_is_google_genai_2x() -> None:
    req = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "google-genai>=2.14.0,<3.0.0" in req
    assert "google-genai>=1.0.0" not in req


def test_lockfile_pins_google_genai_2x() -> None:
    lock = (REPO_ROOT / "requirements.lock").read_text(encoding="utf-8")
    assert "google-genai==2." in lock


def test_gemini_services_use_google_genai_sdk_imports() -> None:
    ai = (REPO_ROOT / "src/domain/services/gemini_ai_service.py").read_text(encoding="utf-8")
    review = (REPO_ROOT / "src/domain/services/gemini_review_service.py").read_text(encoding="utf-8")
    for body in (ai, review):
        assert "from google import genai" in body
        assert "from google.genai import types" in body
        assert "USE_GOOGLE_GENAI" in body
