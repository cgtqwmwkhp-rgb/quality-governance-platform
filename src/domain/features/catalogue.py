"""The feature flags this product tells its own frontend about, as a reviewable literal.

Why this file exists
--------------------
The frontend used to guess. ``useFeatureFlag`` resolved against a hardcoded
defaults map and an object (``window.__FEATURE_FLAGS__``) that nothing anywhere
populated, so no deployment could show a flagged feature without someone typing
into a browser console. Meanwhile the backend knew the answer perfectly well:
``settings.compliance_schedule_enabled`` and the kill switch already decide
whether the API answers at all. This registry is the list of flags the backend is
willing to state an opinion on, and ``GET /api/v1/meta/features`` is where it
states it.

Why an allowlist and not "every boolean in Settings"
----------------------------------------------------
:mod:`src.core.config` mixes UI openers with operational and security
configuration — ``allow_local_password_login``, ``library_disposal_execute``,
``azure_document_intelligence_enable_prod``. Enumerating those to an
unauthenticated caller would be a real disclosure. An allowlist means a flag
reaches the wire only because somebody put it here on purpose.

The failure mode of an allowlist is forgetting to register a flag, which shows up
as a feature that never appears in the UI. That is the benign direction, and
``tests/unit/test_client_feature_catalogue.py`` catches the mechanical half of it
(a ``settings_attr`` that no longer resolves, a permission that is not enforced).
Whether a newly added setting *ought* to be a client flag is a human judgement no
test can infer.

Why a literal and not something generated
-----------------------------------------
Same reason as :mod:`src.domain.authz.catalogue`: a catalogue computed from the
code cannot disagree with the code, so the test guarding it would pass no matter
what. A literal makes registering a flag a reviewable diff.

The three gates
---------------
A feature is reported enabled only when all of its configured gates agree. The
two database gates read in opposite directions, because the two mechanisms this
registry describes were built that way and the registry has to say which is which
rather than smooth it over:

``kill_switch_key``
    Subtract-only, matching :mod:`src.domain.services.compliance_schedule_kill_switch`
    and its copilot twin. A row with ``enabled=True`` means *kill*. An absent row
    means not engaged.

``enabling_flag_key``
    Additive, matching ``_ensure_user_management_enabled`` in
    :mod:`src.api.routes.users`. A row with ``enabled=False`` means off. An absent
    row means on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


@dataclass(frozen=True)
class ClientFeature:
    """One flag the backend is prepared to report to a browser.

    ``ui_key`` is canonical: it is the name the frontend passes to
    ``useFeatureFlag`` and the key that appears on the wire. By convention
    ``settings_attr`` is ``f"{ui_key}_enabled"`` and ``kill_switch_key`` is
    ``f"{ui_key}_kill_switch"``; deviations are allowed but must be spelled out
    here so the exception is visible in review.
    """

    ui_key: str
    #: Attribute on :class:`~src.core.config.Settings`. ``None`` means no config gate.
    settings_attr: Optional[str]
    #: Subtract-only ``feature_flags`` row: ``enabled=True`` closes the feature.
    kill_switch_key: Optional[str]
    #: Additive ``feature_flags`` row: ``enabled=False`` closes the feature.
    enabling_flag_key: Optional[str]
    #: Token the caller must hold. ``None`` means the feature is not permission-gated.
    required_permission: Optional[str]
    #: Why this flag is safe to disclose, and what the UI does with it.
    reason: str


CLIENT_FEATURES: Tuple[ClientFeature, ...] = (
    ClientFeature(
        ui_key="compliance_schedule",
        settings_attr="compliance_schedule_enabled",
        kill_switch_key="compliance_schedule_kill_switch",
        enabling_flag_key=None,
        required_permission="compliance_schedule:read",
        reason=(
            "Gates the Compliance Schedule nav entry and its two routes. The API already "
            "returns 404 for every one of its endpoints when this is off, so the flag "
            "discloses nothing the module's own routing does not."
        ),
    ),
    ClientFeature(
        ui_key="compliance_schedule_regulatory_ai",
        settings_attr="compliance_schedule_regulatory_ai_enabled",
        kill_switch_key="compliance_schedule_kill_switch",
        enabling_flag_key=None,
        required_permission="compliance_schedule:update",
        reason=(
            "Gates the 'Suggest with AI' button beside Regulatory basis on the obligation form. "
            "Deliberately borrows Compliance Schedule's own kill switch rather than declaring a "
            "second one: the suggest routes sit on the module's enabled router, so closing the "
            "module already 404s them, and a separate switch would let the nav and the endpoint "
            "disagree. Reported to a browser only to hide a button the API would refuse."
        ),
    ),
    ClientFeature(
        ui_key="admin_user_management",
        settings_attr=None,
        kill_switch_key=None,
        enabling_flag_key="admin_user_management",
        required_permission=None,
        reason=(
            "Gates the /admin/users route and nav entry. Deliberately not permission-gated "
            "here: the call sites are additionally superuser-gated, and reporting it false "
            "on a transient read failure would remove the tooling used to diagnose that "
            "failure while protecting nothing."
        ),
    ),
)

#: Lookup by the name the frontend uses.
CLIENT_FEATURES_BY_KEY: Mapping[str, ClientFeature] = {feature.ui_key: feature for feature in CLIENT_FEATURES}

CLIENT_FEATURE_KEYS: Tuple[str, ...] = tuple(feature.ui_key for feature in CLIENT_FEATURES)


__all__ = [
    "CLIENT_FEATURES",
    "CLIENT_FEATURES_BY_KEY",
    "CLIENT_FEATURE_KEYS",
    "ClientFeature",
]
