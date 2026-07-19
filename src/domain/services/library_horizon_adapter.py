"""Governance Library Wave W3 — AI horizon scan provider adapter.

Default provider is ``stub`` (deterministic, no network). Live providers are
thin wrappers reserved for a follow-up; they must not be exercised in CI.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from src.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HorizonFindingDraft:
    """Normalised finding produced by a horizon provider before persistence."""

    title: str
    summary: str
    source_url: Optional[str] = None
    external_id: Optional[str] = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    provider: str = "stub"


class HorizonProviderProtocol(Protocol):
    name: str

    def scan(self, *, document_id: int, document_title: str, tenant_id: int) -> list[HorizonFindingDraft]:
        """Return 0–N findings for the given document review context."""


class StubHorizonProvider:
    """Deterministic fixture provider — always returns two stable findings."""

    name = "stub"

    def scan(self, *, document_id: int, document_title: str, tenant_id: int) -> list[HorizonFindingDraft]:
        del tenant_id
        return [
            HorizonFindingDraft(
                title="HSE LOLER Approved Code of Practice update",
                summary=(
                    f"Stub horizon signal for document {document_id} "
                    f"('{document_title}'): review LOLER ACOP changes for lifting operations."
                ),
                source_url="https://www.hse.gov.uk/work-equipment-machinery/loler.htm",
                external_id=f"stub-loler-{document_id}",
                raw_payload={"kind": "stub", "topic": "loler", "document_id": document_id},
                provider=self.name,
            ),
            HorizonFindingDraft(
                title="UK GDPR accountability reminder for controlled records",
                summary=(
                    f"Stub horizon signal for document {document_id}: confirm retention and "
                    "access controls still align with UK GDPR accountability principles."
                ),
                source_url="https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/",
                external_id=f"stub-gdpr-{document_id}",
                raw_payload={"kind": "stub", "topic": "gdpr", "document_id": document_id},
                provider=self.name,
            ),
        ]


class NoopLiveHorizonProvider:
    """Placeholder for live providers — logs and returns empty (no network)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def scan(self, *, document_id: int, document_title: str, tenant_id: int) -> list[HorizonFindingDraft]:
        logger.info(
            "Horizon provider=%s skipped live call (thin stub) document_id=%s tenant_id=%s title=%s",
            self.name,
            document_id,
            tenant_id,
            document_title,
        )
        return []


def get_horizon_provider(provider_name: Optional[str] = None) -> HorizonProviderProtocol:
    """Resolve the configured horizon provider (default: stub)."""
    name = (provider_name or getattr(settings, "library_horizon_provider", None) or "stub").strip().lower()
    if name == "stub":
        return StubHorizonProvider()
    if name in {"anthropic", "openai", "perplexity"}:
        return NoopLiveHorizonProvider(name)
    logger.warning("Unknown library_horizon_provider=%s — falling back to stub", name)
    return StubHorizonProvider()
