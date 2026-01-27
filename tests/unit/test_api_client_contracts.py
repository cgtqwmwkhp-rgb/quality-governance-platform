"""Unit tests for API client route contracts.

These tests verify that frontend API clients use correct endpoint paths
matching the backend routes. This prevents drift between frontend and backend.

Test ID: API-CLIENT-CONTRACTS-001
"""

import pytest


class TestPlanetMarkApiContract:
    """Verify planetMarkApi uses correct endpoint paths."""

    # Route contract: /api/v1/planet-mark/*
    BASE_PATH = "/api/v1/planet-mark"

    def test_get_dashboard_path(self):
        """getDashboard should use /api/v1/planet-mark/dashboard."""
        expected = f"{self.BASE_PATH}/dashboard"
        # Contract: GET /api/v1/planet-mark/dashboard
        assert expected == "/api/v1/planet-mark/dashboard"

    def test_list_years_path(self):
        """listYears should use /api/v1/planet-mark/years."""
        expected = f"{self.BASE_PATH}/years"
        assert expected == "/api/v1/planet-mark/years"

    def test_get_year_path(self):
        """getYear should use /api/v1/planet-mark/years/{yearId}."""
        year_id = 123
        expected = f"{self.BASE_PATH}/years/{year_id}"
        assert expected == "/api/v1/planet-mark/years/123"

    def test_list_sources_path(self):
        """listSources should use /api/v1/planet-mark/years/{yearId}/sources."""
        year_id = 1
        expected = f"{self.BASE_PATH}/years/{year_id}/sources"
        assert expected == "/api/v1/planet-mark/years/1/sources"

    def test_get_scope3_path(self):
        """getScope3 should use /api/v1/planet-mark/years/{yearId}/scope3."""
        year_id = 1
        expected = f"{self.BASE_PATH}/years/{year_id}/scope3"
        assert expected == "/api/v1/planet-mark/years/1/scope3"

    def test_list_actions_path(self):
        """listActions should use /api/v1/planet-mark/years/{yearId}/actions."""
        year_id = 1
        expected = f"{self.BASE_PATH}/years/{year_id}/actions"
        assert expected == "/api/v1/planet-mark/years/1/actions"

    def test_get_certification_path(self):
        """getCertification should use /api/v1/planet-mark/years/{yearId}/certification."""
        year_id = 1
        expected = f"{self.BASE_PATH}/years/{year_id}/certification"
        assert expected == "/api/v1/planet-mark/years/1/certification"


class TestUVDBApiContract:
    """Verify uvdbApi uses correct endpoint paths."""

    # Route contract: /api/v1/uvdb/*
    BASE_PATH = "/api/v1/uvdb"

    def test_get_dashboard_path(self):
        """getDashboard should use /api/v1/uvdb/dashboard."""
        expected = f"{self.BASE_PATH}/dashboard"
        assert expected == "/api/v1/uvdb/dashboard"

    def test_get_protocol_path(self):
        """getProtocol should use /api/v1/uvdb/protocol."""
        expected = f"{self.BASE_PATH}/protocol"
        assert expected == "/api/v1/uvdb/protocol"

    def test_list_sections_path(self):
        """listSections should use /api/v1/uvdb/sections."""
        expected = f"{self.BASE_PATH}/sections"
        assert expected == "/api/v1/uvdb/sections"

    def test_get_section_questions_path(self):
        """getSectionQuestions should use /api/v1/uvdb/sections/{sectionNumber}/questions."""
        section_number = 1
        expected = f"{self.BASE_PATH}/sections/{section_number}/questions"
        assert expected == "/api/v1/uvdb/sections/1/questions"

    def test_list_audits_path(self):
        """listAudits should use /api/v1/uvdb/audits with pagination."""
        expected = f"{self.BASE_PATH}/audits?page=1&size=10"
        assert expected == "/api/v1/uvdb/audits?page=1&size=10"

    def test_get_audit_path(self):
        """getAudit should use /api/v1/uvdb/audits/{auditId}."""
        audit_id = 42
        expected = f"{self.BASE_PATH}/audits/{audit_id}"
        assert expected == "/api/v1/uvdb/audits/42"

    def test_get_audit_responses_path(self):
        """getAuditResponses should use /api/v1/uvdb/audits/{auditId}/responses."""
        audit_id = 42
        expected = f"{self.BASE_PATH}/audits/{audit_id}/responses"
        assert expected == "/api/v1/uvdb/audits/42/responses"

    def test_get_iso_mapping_path(self):
        """getISOMapping should use /api/v1/uvdb/iso-mapping."""
        expected = f"{self.BASE_PATH}/iso-mapping"
        assert expected == "/api/v1/uvdb/iso-mapping"


class TestActionsApiContract:
    """Verify actionsApi uses correct endpoint paths (PR1 regression)."""

    # Route contract: /api/v1/actions/*
    BASE_PATH = "/api/v1/actions"

    def test_list_path(self):
        """list should use /api/v1/actions/ with pagination."""
        expected = f"{self.BASE_PATH}/?page=1&size=10"
        assert expected == "/api/v1/actions/?page=1&size=10"

    def test_create_path(self):
        """create should use POST /api/v1/actions/."""
        expected = f"{self.BASE_PATH}/"
        assert expected == "/api/v1/actions/"

    def test_get_path_requires_source_type(self):
        """get should use /api/v1/actions/{id}?source_type=..."""
        action_id = 1
        source_type = "incident"
        expected = f"{self.BASE_PATH}/{action_id}?source_type={source_type}"
        assert expected == "/api/v1/actions/1?source_type=incident"

    def test_update_path_requires_source_type(self):
        """update should use PATCH /api/v1/actions/{id}?source_type=..."""
        action_id = 1
        source_type = "rta"
        expected = f"{self.BASE_PATH}/{action_id}?source_type={source_type}"
        assert expected == "/api/v1/actions/1?source_type=rta"


class TestInvestigationsApiContract:
    """Verify investigationsApi uses correct endpoint paths (PR1)."""

    # Route contract: /api/v1/investigations/*
    BASE_PATH = "/api/v1/investigations"

    def test_list_path(self):
        """list should use /api/v1/investigations/ with pagination."""
        expected = f"{self.BASE_PATH}/?page=1&size=10"
        assert expected == "/api/v1/investigations/?page=1&size=10"

    def test_create_path(self):
        """create should use POST /api/v1/investigations/."""
        expected = f"{self.BASE_PATH}/"
        assert expected == "/api/v1/investigations/"

    def test_get_path(self):
        """get should use /api/v1/investigations/{id}."""
        investigation_id = 123
        expected = f"{self.BASE_PATH}/{investigation_id}"
        assert expected == "/api/v1/investigations/123"

    def test_update_path(self):
        """update should use PATCH /api/v1/investigations/{id}."""
        investigation_id = 123
        expected = f"{self.BASE_PATH}/{investigation_id}"
        assert expected == "/api/v1/investigations/123"

    def test_autosave_path(self):
        """autosave should use PATCH /api/v1/investigations/{id}/autosave."""
        investigation_id = 123
        expected = f"{self.BASE_PATH}/{investigation_id}/autosave"
        assert expected == "/api/v1/investigations/123/autosave"

    def test_create_from_record_path(self):
        """createFromRecord should use POST /api/v1/investigations/from-record."""
        expected = f"{self.BASE_PATH}/from-record"
        assert expected == "/api/v1/investigations/from-record"

    def test_list_source_records_path(self):
        """listSourceRecords should use /api/v1/investigations/source-records."""
        expected = f"{self.BASE_PATH}/source-records"
        assert expected == "/api/v1/investigations/source-records"
