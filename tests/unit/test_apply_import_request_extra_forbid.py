"""B-10: ApplyImportRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.planet_mark import ApplyImportRequest


def test_apply_import_request_accepts_known_fields() -> None:
    m = ApplyImportRequest(import_job_id=12, reporting_year_id=3, overwrite_existing=True)
    assert m.import_job_id == 12
    assert m.reporting_year_id == 3
    assert m.overwrite_existing is True


def test_apply_import_request_defaults() -> None:
    m = ApplyImportRequest(import_job_id=1)
    assert m.reporting_year_id is None
    assert m.overwrite_existing is False


def test_apply_import_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ApplyImportRequest(
            import_job_id=1,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
