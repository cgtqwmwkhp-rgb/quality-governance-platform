"""Path-to-10: src.services.external_audit_import_service is a dual-service re-export."""

from pathlib import Path

from src.domain.services import external_audit_import_service as domain_mod
from src.services import external_audit_import_service as services_mod

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_external_audit_import_service_reexport_is_domain_canonical():
    assert services_mod.ExternalAuditImportService is domain_mod.ExternalAuditImportService
    assert services_mod.PromotionResult is domain_mod.PromotionResult
    assert services_mod.PROCESSING_TTL_SECONDS is domain_mod.PROCESSING_TTL_SECONDS
    assert services_mod.MAX_SOURCE_FILE_BYTES is domain_mod.MAX_SOURCE_FILE_BYTES


def test_external_audit_import_service_constructs_with_session():
    class _DummySession:
        pass

    svc = services_mod.ExternalAuditImportService(_DummySession())
    assert svc is not None
    assert svc.db is not None


def test_external_audit_import_routes_prefer_dual_service_path():
    body = (REPO_ROOT / "src/api/routes/external_audit_imports.py").read_text(encoding="utf-8")
    assert "from src.services.external_audit_import_service import ExternalAuditImportService" in body
    assert "from src.domain.services.external_audit_import_service import ExternalAuditImportService" not in body


def test_external_audit_import_tasks_prefer_dual_service_path():
    body = (REPO_ROOT / "src/infrastructure/tasks/external_audit_import_tasks.py").read_text(encoding="utf-8")
    assert "from src.services.external_audit_import_service import ExternalAuditImportService" in body
    assert "from src.domain.services.external_audit_import_service import ExternalAuditImportService" not in body


def test_external_audit_import_unit_tests_prefer_dual_service_path():
    body = (REPO_ROOT / "tests/unit/test_external_audit_import_service.py").read_text(encoding="utf-8")
    assert (
        "from src.services.external_audit_import_service import PROCESSING_TTL_SECONDS, ExternalAuditImportService"
        in body
    )
    assert (
        "from src.domain.services.external_audit_import_service import PROCESSING_TTL_SECONDS, ExternalAuditImportService"
        not in body
    )


def test_external_audit_import_integration_tests_prefer_dual_service_path():
    body = (REPO_ROOT / "tests/integration/test_external_audit_imports_api.py").read_text(encoding="utf-8")
    assert "from src.services.external_audit_import_service import ExternalAuditImportService" in body
    assert "from src.domain.services.external_audit_import_service import ExternalAuditImportService" not in body
