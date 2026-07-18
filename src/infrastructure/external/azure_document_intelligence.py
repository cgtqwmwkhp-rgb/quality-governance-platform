"""Compatibility shim — Azure DI client lives in domain (import-boundary safe).

E4 DPO gate: live analyze requires credentials AND AZURE_DOCUMENT_INTELLIGENCE_ENABLE_PROD.
"""

from src.domain.services.azure_document_intelligence_service import (
    AzureDocumentIntelligenceClient,
    AzureDocumentIntelligenceResult,
    AzureDocumentPage,
    get_azure_di_readiness,
)

__all__ = [
    "AzureDocumentIntelligenceClient",
    "AzureDocumentIntelligenceResult",
    "AzureDocumentPage",
    "get_azure_di_readiness",
]
