"""Regression tests for external audit import schema migrations."""

import re
from pathlib import Path

ALEMBIC_VERSIONS_DIR = Path("alembic/versions")


def _migration_texts() -> list[tuple[str, str]]:
    return [(path.name, path.read_text(encoding="utf-8")) for path in sorted(ALEMBIC_VERSIONS_DIR.glob("*.py"))]


def _has_create_table(text: str, table_name: str) -> bool:
    pattern = rf"create_table\(\s*[\"']{table_name}[\"']"
    return re.search(pattern, text, flags=re.MULTILINE) is not None


def test_external_audit_import_jobs_table_has_a_create_table_migration():
    """The import jobs table must be created by Alembic, not only SQLAlchemy metadata."""
    matching_files = [
        name for name, text in _migration_texts() if _has_create_table(text, "external_audit_import_jobs")
    ]
    assert matching_files, "Missing Alembic create_table migration for external_audit_import_jobs"


def test_external_audit_import_drafts_table_has_a_create_table_migration():
    """The import drafts table must be created by Alembic for production parity."""
    matching_files = [
        name for name, text in _migration_texts() if _has_create_table(text, "external_audit_import_drafts")
    ]
    assert matching_files, "Missing Alembic create_table migration for external_audit_import_drafts"


def test_external_audit_import_create_table_migration_postdates_enhancement_migration():
    """The repo must include a recovery migration after the enhancement-only revision."""
    create_migrations = [
        name for name, text in _migration_texts() if _has_create_table(text, "external_audit_import_jobs")
    ]
    assert any(name > "20260327_enhance_external_audit_import_jobs.py" for name in create_migrations)
