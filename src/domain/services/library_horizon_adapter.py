"""Governance Library Wave W3 — AI horizon scan provider adapter.

Default provider is ``stub`` (deterministic, no network). Perplexity is a live
provider when ``perplexity_api_key`` is configured; other live names remain noop.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

import httpx

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


class PerplexityLiveHorizonProvider:
    """Live Perplexity research — fail-closed to empty list on any error."""

    name = "perplexity"
    _API_URL = "https://api.perplexity.ai/chat/completions"

    def __init__(self, api_key: str) -> None:
        self._api_key = (api_key or "").strip()

    def scan(self, *, document_id: int, document_title: str, tenant_id: int) -> list[HorizonFindingDraft]:
        query = (
            f"Regulatory and best-practice horizon for controlled document "
            f"'{document_title}' (id={document_id}, tenant={tenant_id}). "
            "Return JSON array of up to 5 objects with keys title, summary, source_url."
        )
        return self.research(query)

    def research(self, query: str) -> list[HorizonFindingDraft]:
        if not self._api_key:
            logger.info("Perplexity research skipped — no API key")
            return []
        try:
            payload = {
                "model": "sonar",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a UK H&S / ISO compliance researcher. "
                            "Respond with JSON only: an array of objects with "
                            "title, summary, source_url. Prefer official HSE/ISO/ICO sources."
                        ),
                    },
                    {"role": "user", "content": query[:4000]},
                ],
                "temperature": 0.2,
                "max_tokens": 1200,
            }
            with httpx.Client(timeout=25.0) as client:
                resp = client.post(
                    self._API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                resp.raise_for_status()
                body = resp.json()
            text = ((((body.get("choices") or [{}])[0].get("message") or {}).get("content")) or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            data = json.loads(text)
            if not isinstance(data, list):
                return []
            findings: list[HorizonFindingDraft] = []
            for i, item in enumerate(data[:8]):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                summary = str(item.get("summary") or "").strip()
                url = str(item.get("source_url") or "").strip() or None
                if not title or not summary:
                    continue
                if url and not (url.startswith("http://") or url.startswith("https://")):
                    url = None
                findings.append(
                    HorizonFindingDraft(
                        title=title[:300],
                        summary=summary[:2000],
                        source_url=url,
                        external_id=f"pplx-{i}-{abs(hash(title)) % 10_000_000}",
                        raw_payload={"kind": "perplexity", "item": item},
                        provider=self.name,
                    )
                )
            return findings
        except (httpx.HTTPError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
            logger.info("Perplexity research unavailable: %s", type(exc).__name__)
            return []
        except Exception as exc:  # noqa: BLE001 — fail-closed
            logger.info("Perplexity research failed: %s", type(exc).__name__)
            return []


def get_horizon_provider(provider_name: Optional[str] = None) -> HorizonProviderProtocol:
    """Resolve the configured horizon provider (default: stub)."""
    name = (provider_name or getattr(settings, "library_horizon_provider", None) or "stub").strip().lower()
    if name == "stub":
        return StubHorizonProvider()
    if name == "perplexity":
        key = getattr(settings, "perplexity_api_key", "") or ""
        if key.strip():
            return PerplexityLiveHorizonProvider(key)
        logger.info("library_horizon_provider=perplexity but key missing — noop")
        return NoopLiveHorizonProvider("perplexity")
    if name in {"anthropic", "openai"}:
        return NoopLiveHorizonProvider(name)
    logger.warning("Unknown library_horizon_provider=%s — falling back to stub", name)
    return StubHorizonProvider()


def research_with_perplexity(query: str) -> list[HorizonFindingDraft]:
    """Convenience for Audit Builder research — uses key even if horizon provider is stub."""
    key = getattr(settings, "perplexity_api_key", "") or ""
    if not key.strip():
        return []
    return PerplexityLiveHorizonProvider(key).research(query)
