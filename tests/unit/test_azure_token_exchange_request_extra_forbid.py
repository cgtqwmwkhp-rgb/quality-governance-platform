"""B-10: AzureTokenExchangeRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.auth import AzureTokenExchangeRequest


def test_azure_token_exchange_request_accepts_known_fields() -> None:
    m = AzureTokenExchangeRequest(id_token="eyJhbGciOiJSUzI1NiJ9.example")
    assert m.id_token.startswith("eyJ")


def test_azure_token_exchange_request_requires_id_token() -> None:
    with pytest.raises(ValidationError):
        AzureTokenExchangeRequest()  # type: ignore[call-arg]


def test_azure_token_exchange_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AzureTokenExchangeRequest(
            id_token="eyJhbGciOiJSUzI1NiJ9.example",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
