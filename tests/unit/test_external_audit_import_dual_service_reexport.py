"""Path-to-10: src.services.external_audit_import_service is a dual-service re-export."""

from src.domain.services import external_audit_import_service as domain_mod
from src.services import external_audit_import_service as services_mod


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
