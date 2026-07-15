"""Unit tests for the PAMS-to-QGP asset mapping scaffold."""

from src.domain.services.pams_asset_mapping_service import (
    PamsAssetCandidate,
    PamsAssetMappingService,
    normalise_asset_reference,
)


def test_normalise_asset_reference_removes_common_registration_separators():
    assert normalise_asset_reference(" ab12-cde ") == "AB12CDE"
    assert normalise_asset_reference(None) == ""


def test_resolve_matches_vehicle_registration_in_current_tenant():
    result = PamsAssetMappingService().resolve(
        {"vanReg": "AB12 CDE"},
        [
            PamsAssetCandidate(id=4, tenant_id=21, asset_number="VAN-04", vehicle_reg="AB12-CDE"),
            PamsAssetCandidate(id=5, tenant_id=22, asset_number="VAN-05", vehicle_reg="AB12-CDE"),
        ],
        tenant_id=21,
    )

    assert result is not None
    assert result.asset_id == 4
    assert result.matched_reference == "AB12CDE"


def test_resolve_refuses_ambiguous_or_empty_references():
    service = PamsAssetMappingService()
    candidates = [
        PamsAssetCandidate(id=4, tenant_id=21, asset_number="VAN-04", vehicle_reg="AB12-CDE"),
        PamsAssetCandidate(id=6, tenant_id=21, asset_number="VAN-06", vehicle_reg="AB12 CDE"),
    ]

    assert service.resolve({"vanReg": "AB12 CDE"}, candidates, tenant_id=21) is None
    assert service.resolve({}, candidates, tenant_id=21) is None
