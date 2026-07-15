"""Deterministic, tenant-safe matching for PAMS checklist asset references.

This is intentionally a pure service: sync jobs can use it before persisting an
``asset_id`` without coupling the PAMS import path to a particular database
session or QR/portal route.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

PAMS_ASSET_REFERENCE_KEYS = ("assetId", "asset_id", "assetNumber", "asset_number", "vanReg", "VehicleReg", "reg")


def normalise_asset_reference(value: object | None) -> str:
    """Normalise identifiers while preserving the meaningful alphanumeric text."""
    if value is None:
        return ""
    return "".join(character for character in str(value).upper() if character.isalnum())


@dataclass(frozen=True)
class PamsAssetCandidate:
    """The asset fields that can safely participate in a PAMS lookup."""

    id: int
    tenant_id: int | None
    asset_number: str
    vehicle_reg: str | None = None


@dataclass(frozen=True)
class PamsAssetMapping:
    """Resolved local asset ID and the PAMS value that established the link."""

    asset_id: int
    matched_reference: str


class PamsAssetMappingService:
    """Resolve only unambiguous PAMS references within the current tenant."""

    def resolve(
        self,
        pams_row: dict[str, Any],
        candidates: Iterable[PamsAssetCandidate],
        *,
        tenant_id: int,
    ) -> PamsAssetMapping | None:
        """Return a mapping when exactly one tenant-scoped candidate matches.

        A blank reference, cross-tenant candidate, or duplicate match returns
        ``None`` so sync callers retain the current unmapped behaviour rather
        than attaching a checklist to the wrong asset.
        """
        references = {
            normalise_asset_reference(pams_row.get(key))
            for key in PAMS_ASSET_REFERENCE_KEYS
            if normalise_asset_reference(pams_row.get(key))
        }
        if not references:
            return None

        matches = [
            candidate
            for candidate in candidates
            if candidate.tenant_id == tenant_id
            and (
                normalise_asset_reference(candidate.asset_number) in references
                or normalise_asset_reference(candidate.vehicle_reg) in references
            )
        ]
        if len(matches) != 1:
            return None

        candidate = matches[0]
        matched_reference = next(
            reference
            for reference in references
            if reference
            in {
                normalise_asset_reference(candidate.asset_number),
                normalise_asset_reference(candidate.vehicle_reg),
            }
        )
        return PamsAssetMapping(asset_id=candidate.id, matched_reference=matched_reference)
