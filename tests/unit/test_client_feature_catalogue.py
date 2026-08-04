"""The client feature registry must stay wired to the things it names.

None of these assertions can tell you whether a new setting *should* be a client
flag — that is a judgement. What they catch is the mechanical half: a registry
entry pointing at a setting that has been renamed, a permission token that is not
actually enforced, or a kill switch that nothing can read. Each of those would
otherwise surface as a feature that is silently and permanently invisible, which
is indistinguishable from the bug this channel was built to fix.
"""

from __future__ import annotations

from src.core.config import Settings
from src.domain.authz.catalogue import ENFORCED_PERMISSIONS
from src.domain.features.catalogue import CLIENT_FEATURES, CLIENT_FEATURES_BY_KEY
from src.domain.features.evaluator import kill_switch_reader_keys


def test_ui_keys_are_unique():
    keys = [feature.ui_key for feature in CLIENT_FEATURES]
    assert len(keys) == len(set(keys)), f"duplicate ui_key in CLIENT_FEATURES: {keys}"
    assert len(CLIENT_FEATURES_BY_KEY) == len(CLIENT_FEATURES)


def test_every_settings_attr_resolves():
    """A renamed setting must fail here, not silently report the feature closed.

    Checked against ``model_fields`` rather than ``hasattr``: Pydantic v2 declares
    fields on the model, not as class attributes, so ``hasattr`` on the class is
    false for every real setting.
    """
    declared = set(Settings.model_fields)
    missing = sorted(
        feature.settings_attr
        for feature in CLIENT_FEATURES
        if feature.settings_attr is not None and feature.settings_attr not in declared
    )
    assert not missing, f"CLIENT_FEATURES name settings that do not exist on Settings: {missing}"


def test_every_required_permission_is_enforced():
    """Folding in a token nothing enforces would hide a feature for no reason."""
    unknown = sorted(
        feature.required_permission
        for feature in CLIENT_FEATURES
        if feature.required_permission is not None and feature.required_permission not in ENFORCED_PERMISSIONS
    )
    assert not unknown, f"CLIENT_FEATURES require permissions absent from ENFORCED_PERMISSIONS: {unknown}"


def test_every_kill_switch_has_a_reader():
    """A registry entry naming an unreadable switch reports the feature closed."""
    readers = kill_switch_reader_keys()
    unwired = sorted(
        feature.kill_switch_key
        for feature in CLIENT_FEATURES
        if feature.kill_switch_key is not None and feature.kill_switch_key not in readers
    )
    assert not unwired, f"CLIENT_FEATURES name kill switches with no reader: {unwired}"


def test_naming_convention_holds_or_is_deliberate():
    """settings_attr and kill_switch_key follow from ui_key unless stated otherwise.

    The convention is not enforced as a hard rule because deviations are legitimate,
    but an entry that breaks it must carry a reason long enough to explain itself.
    """
    for feature in CLIENT_FEATURES:
        if feature.settings_attr is not None and feature.settings_attr != f"{feature.ui_key}_enabled":
            assert len(feature.reason.strip()) >= 40, (
                f"{feature.ui_key} deviates from the settings_attr convention "
                f"({feature.settings_attr!r}) without explaining why"
            )
        if feature.kill_switch_key is not None and feature.kill_switch_key != f"{feature.ui_key}_kill_switch":
            assert len(feature.reason.strip()) >= 40, (
                f"{feature.ui_key} deviates from the kill_switch_key convention "
                f"({feature.kill_switch_key!r}) without explaining why"
            )


def test_every_feature_explains_itself():
    """The reason is what a reviewer reads when deciding whether disclosure is safe."""
    vague = sorted(feature.ui_key for feature in CLIENT_FEATURES if len(feature.reason.strip()) < 40)
    assert not vague, f"CLIENT_FEATURES entries with no meaningful reason: {vague}"


def test_no_operational_settings_are_exposed():
    """The allowlist exists to keep security and destructive config off the wire."""
    forbidden = {
        "allow_local_password_login",
        "library_disposal_execute",
        "azure_document_intelligence_enable_prod",
    }
    leaked = sorted(
        feature.settings_attr
        for feature in CLIENT_FEATURES
        if feature.settings_attr is not None and feature.settings_attr in forbidden
    )
    assert not leaked, f"operational settings must never be client features: {leaked}"


def test_compliance_schedule_is_registered_with_its_permission():
    """The feature this channel was built for, asserted explicitly."""
    feature = CLIENT_FEATURES_BY_KEY["compliance_schedule"]
    assert feature.settings_attr == "compliance_schedule_enabled"
    assert feature.kill_switch_key == "compliance_schedule_kill_switch"
    assert feature.required_permission == "compliance_schedule:read"
