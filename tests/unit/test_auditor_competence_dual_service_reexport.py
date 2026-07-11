"""Path-to-10: src.services.auditor_competence is a dual-service re-export."""

from src.domain.services import auditor_competence as domain_mod
from src.services import auditor_competence as services_mod


def test_auditor_competence_services_reexport_domain_classes():
    assert services_mod.AuditorCompetenceService is domain_mod.AuditorCompetenceService
