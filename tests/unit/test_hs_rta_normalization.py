from src.domain.services.hs_rta_normalization import normalize_rta_collision_type


def test_normalizes_known_excel_collision_types():
    assert normalize_rta_collision_type("Rear-End") == "rear_end"
    assert normalize_rta_collision_type("Side impact") == "side_impact"
    assert normalize_rta_collision_type(" Unknown Type ") == "unknown_type"
    assert normalize_rta_collision_type(None) is None
