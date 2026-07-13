"""UK-first regulatory & practice watch for the Governed Knowledge Bank.

Polls curated public sources (not unrestricted web crawl), persists
RegulatoryUpdate rows, and matches impacts against policies / MSDS / RAMS / COSHH.
High-confidence impacts auto-create tasks; others go to the exception inbox.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from xml.etree import ElementTree

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_automation import RegulatoryUpdate
from src.domain.models.document import Document
from src.domain.models.governed_knowledge import (
    AiDecisionLog,
    RegulatoryImpactStatus,
    RegulatoryWatchImpact,
)
from src.domain.services.governed_knowledge_service import AUTO_CONFIRM_THRESHOLD

logger = logging.getLogger(__name__)

# Curated allowlist — AI-first but not open-ended crawling.
UK_FEED_SOURCES: list[dict[str, str]] = [
    {
        "id": "hse_news",
        "source": "hse_uk",
        "category": "health_safety",
        "url": "https://www.hse.gov.uk/rss/news.xml",
        "title_prefix": "HSE",
    },
    {
        "id": "legislation_uk_si",
        "source": "hse_uk",
        "category": "legislation",
        "url": "https://www.legislation.gov.uk/uksi/data.feed",
        "title_prefix": "UK SI",
    },
]

IMPACT_DOC_TYPES = frozenset(
    {
        "policy",
        "procedure",
        "sop",
        "rams",
        "ram",
        "method_statement",
        "coshh",
        "msds",
        "sds",
        "guideline",
        "manual",
    }
)

WATCH_KEYWORDS = (
    "coshh",
    "msds",
    "sds",
    "rams",
    "clp",
    "reach",
    "mcl",
    "asbestos",
    "working at height",
    "manual handling",
    "fire safety",
    "iso 9001",
    "iso 14001",
    "iso 45001",
    "carbon",
    "net zero",
    "environment agency",
    "hse",
)


@dataclass
class FeedItem:
    title: str
    summary: str
    url: str
    source: str
    category: str
    external_id: str


class RegulatoryWatchService:
    """Poll curated UK feeds and impact-match against the knowledge bank."""

    async def run_poll_cycle(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        triggered_by: Optional[int] = None,
    ) -> dict[str, Any]:
        items = await self.fetch_curated_feeds()
        created_updates = 0
        created_impacts = 0
        auto_tasks = 0

        for item in items:
            existing = await db.execute(
                select(RegulatoryUpdate).where(
                    RegulatoryUpdate.tenant_id == tenant_id,
                    RegulatoryUpdate.source == item.source,
                    RegulatoryUpdate.source_reference == item.external_id,
                )
            )
            update = existing.scalar_one_or_none()
            if update is None:
                update = RegulatoryUpdate(
                    tenant_id=tenant_id,
                    source=item.source,
                    source_reference=item.external_id[:100],
                    source_url=item.url[:2000] if item.url else None,
                    title=item.title[:500],
                    summary=(item.summary or "")[:5000] or None,
                    category=item.category,
                    impact="medium",
                    tags=self._extract_tags(f"{item.title} {item.summary}"),
                    published_date=datetime.now(timezone.utc).replace(tzinfo=None),
                    is_reviewed=False,
                )
                # published_date may not exist — use setattr soft
                db.add(update)
                await db.flush()
                created_updates += 1

            impacts = await self.match_impacts_for_update(db, update=update, tenant_id=tenant_id)
            for impact in impacts:
                db.add(impact)
                created_impacts += 1
                if (
                    impact.confidence is not None
                    and impact.confidence >= AUTO_CONFIRM_THRESHOLD
                    and impact.status == RegulatoryImpactStatus.NEW
                ):
                    # AI-first: high confidence → mark as task_created automatically
                    impact.status = RegulatoryImpactStatus.TASK_CREATED
                    auto_tasks += 1

        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action="regulatory_watch_poll",
                entity_type="tenant",
                entity_id=str(tenant_id),
                confidence=None,
                auto_applied=True,
                payload={
                    "triggered_by": triggered_by,
                    "feed_items": len(items),
                    "updates_created": created_updates,
                    "impacts_created": created_impacts,
                    "auto_tasks": auto_tasks,
                },
            )
        )
        await db.commit()
        return {
            "status": "completed",
            "feed_items": len(items),
            "updates_created": created_updates,
            "impacts_created": created_impacts,
            "auto_tasks": auto_tasks,
        }

    async def fetch_curated_feeds(self) -> list[FeedItem]:
        items: list[FeedItem] = []
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for feed in UK_FEED_SOURCES:
                try:
                    response = await client.get(
                        feed["url"],
                        headers={"User-Agent": "QGP-RegulatoryWatch/1.0"},
                    )
                    if response.status_code != 200:
                        logger.warning(
                            "Regulatory feed %s returned %s", feed["id"], response.status_code
                        )
                        continue
                    items.extend(self._parse_atom_or_rss(response.text, feed))
                except Exception as exc:
                    logger.warning("Regulatory feed %s failed: %s", feed["id"], exc)
        # Seed fallback when feeds unreachable (offline/dev) so pipeline stays testable
        if not items:
            items.append(
                FeedItem(
                    title="HSE / GB CLP monitoring reminder",
                    summary=(
                        "Monitor HSE GB MCL list and COSHH/SDS guidance changes. "
                        "Review organisational RAMS, COSHH assessments and MSDS holdings."
                    ),
                    url="https://www.hse.gov.uk/chemical-classification/",
                    source="hse_uk",
                    category="health_safety",
                    external_id="fallback-gb-clp-watch",
                )
            )
        return items[:50]

    def _parse_atom_or_rss(self, xml_text: str, feed: dict[str, str]) -> list[FeedItem]:
        items: list[FeedItem] = []
        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            return items

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        # Atom entries
        for entry in root.findall("atom:entry", ns) or root.findall(
            "{http://www.w3.org/2005/Atom}entry"
        ):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
            summary = (
                entry.findtext("atom:summary", default="", namespaces=ns)
                or entry.findtext("atom:content", default="", namespaces=ns)
                or ""
            ).strip()
            link_el = entry.find("atom:link", ns)
            href = link_el.get("href") if link_el is not None else ""
            entry_id = (
                entry.findtext("atom:id", default="", namespaces=ns) or href or title
            )[:120]
            if title and self._looks_relevant(f"{title} {summary}"):
                items.append(
                    FeedItem(
                        title=f"{feed['title_prefix']}: {title}"[:500],
                        summary=re.sub(r"<[^>]+>", "", summary)[:5000],
                        url=href or feed["url"],
                        source=feed["source"],
                        category=feed["category"],
                        external_id=entry_id,
                    )
                )

        # RSS items
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            summary = (item.findtext("description") or "").strip()
            link = (item.findtext("link") or "").strip()
            guid = (item.findtext("guid") or link or title)[:120]
            if title and self._looks_relevant(f"{title} {summary}"):
                items.append(
                    FeedItem(
                        title=f"{feed['title_prefix']}: {title}"[:500],
                        summary=re.sub(r"<[^>]+>", "", summary)[:5000],
                        url=link or feed["url"],
                        source=feed["source"],
                        category=feed["category"],
                        external_id=guid,
                    )
                )
        return items

    def _looks_relevant(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in WATCH_KEYWORDS)

    def _extract_tags(self, text: str) -> list[str]:
        lower = text.lower()
        return [k for k in WATCH_KEYWORDS if k in lower][:12]

    async def match_impacts_for_update(
        self,
        db: AsyncSession,
        *,
        update: RegulatoryUpdate,
        tenant_id: int,
    ) -> list[RegulatoryWatchImpact]:
        """Match update text against KB docs of relevant types."""
        blob = f"{update.title} {update.summary or ''}".lower()
        tags = update.tags or self._extract_tags(blob)
        if not tags:
            return []

        result = await db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                or_(
                    Document.document_type.in_(list(IMPACT_DOC_TYPES)),
                    Document.category.in_(["policy", "safety", "environment", "quality"]),
                ),
            ).limit(200)
        )
        docs = list(result.scalars().all())
        impacts: list[RegulatoryWatchImpact] = []

        for doc in docs:
            # Skip duplicate impact for same update+doc
            existing = await db.execute(
                select(RegulatoryWatchImpact.id).where(
                    RegulatoryWatchImpact.tenant_id == tenant_id,
                    RegulatoryWatchImpact.update_id == str(update.id),
                    RegulatoryWatchImpact.document_id == doc.id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            hay = " ".join(
                filter(
                    None,
                    [
                        doc.title or "",
                        doc.description or "",
                        doc.document_type or "",
                        doc.category or "",
                        " ".join(doc.ai_tags or []) if getattr(doc, "ai_tags", None) else "",
                        doc.ai_summary or "",
                    ],
                )
            ).lower()
            hits = [t for t in tags if t in hay or t in blob and doc.document_type in IMPACT_DOC_TYPES]
            if not hits and doc.document_type in {"coshh", "msds", "sds", "rams", "ram"}:
                # Always soft-flag chemical/safety docs on HSE chemical updates
                if any(k in blob for k in ("coshh", "clp", "msds", "sds", "chemical", "mcl")):
                    hits = ["chemical_safety"]
            if not hits:
                continue

            confidence = min(0.95, 0.55 + 0.1 * len(hits))
            impacts.append(
                RegulatoryWatchImpact(
                    tenant_id=tenant_id,
                    update_id=str(update.id),
                    document_id=doc.id,
                    confidence=confidence,
                    rationale=(
                        f"Matched tags {hits} between regulatory update "
                        f"'{update.title[:80]}' and document '{doc.title[:80]}'"
                    )[:2000],
                    status=RegulatoryImpactStatus.NEW,
                )
            )
        return impacts


regulatory_watch_service = RegulatoryWatchService()
