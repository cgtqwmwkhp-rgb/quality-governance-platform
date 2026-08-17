"""ISO NEAR proposed-share for Standards matrix cells (AP-07).

NEAR is not EXACT. Apply writes PROPOSED + auto_applied links so coverage
does not count until an operator confirms the required addition. CE↔CE+
NEAR and scheme columns (CHAS / SSIP / PM / UVDB) are out of this slice.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.services.standards_exact_share_service import ExactSharePlan, ExactShareService
from src.domain.services.standards_trap_guard import ISO_NUMBERING_FAMILY

NearSharePlan = ExactSharePlan


class NearShareService(ExactShareService):
    """Plan / apply / undo ISO-family NEAR evidence proposals."""

    share_verdict = "NEAR"
    share_label = "NEAR"
    unavailable_no_peers = "no_iso_near_peers"
    not_peer_reason = "not_iso_near_peer"
    conflict_prefix = "NEAR_SHARE"

    def _select_peers(self, annotation: dict[str, Any], *, source_framework: str) -> list[dict[str, Any]]:
        source_fw = (source_framework or "").strip().lower()
        if source_fw not in ISO_NUMBERING_FAMILY:
            return []
        peers: list[dict[str, Any]] = []
        for peer in annotation.get("peers") or []:
            if str(peer.get("verdict") or "").upper() != "NEAR":
                continue
            peer_fw = str(peer.get("framework") or "").strip().lower()
            if peer_fw not in ISO_NUMBERING_FAMILY:
                continue
            peers.append(peer)
        return peers

    def _share_notes(
        self,
        source_link: ComplianceEvidenceLink,
        resolved: Sequence[dict[str, Any]],
    ) -> Optional[str]:
        additions: list[str] = []
        seen: set[str] = set()
        for row in resolved:
            text = str(row.get("addition_text") or "").strip()
            if text and text not in seen:
                seen.add(text)
                additions.append(text)
        header = (
            "NEAR share — not EXACT. Required addition: " + " | ".join(additions)
            if additions
            else "NEAR share — not EXACT. Confirm after the required addition is in the deliverable."
        )
        existing = (source_link.notes or "").strip()
        return f"{header}\n{existing}" if existing else header
