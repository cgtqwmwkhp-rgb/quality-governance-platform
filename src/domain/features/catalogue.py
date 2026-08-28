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

``requires_ui_key``
    Another registered feature that must itself be open. For a flag whose own
    setting is a *second* opener on top of a master switch — ``AI_COPILOT_INFERENCE_ENABLED``
    on top of ``AI_COPILOT_ENABLED`` — reporting the second opener alone would put
    a value on the wire that says a capability is live when the surface carrying it
    is closed. The frontend would have to know to AND them, which is the guessing
    this channel exists to stop.
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
    #: Another ``ui_key`` in this registry that must also be open. Must be declared
    #: earlier in :data:`CLIENT_FEATURES`, and must not itself require anything.
    requires_ui_key: Optional[str] = None


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
        ui_key="compliance_schedule_fra_ocr",
        settings_attr="compliance_schedule_fra_ocr_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="compliance_schedule:update",
        reason=(
            "Gates the FRA OCR upload and review panel on the Compliance Schedule detail "
            "page. No kill switch of its own: the routes hang off the module's enabled "
            "router, so compliance_schedule_kill_switch already closes them, and a second "
            "switch would need a reader in features/evaluator.py that reports nothing the "
            "first does not. Permission-gated on :update rather than :read because a "
            "read-only user can do nothing with the panel but look at it."
        ),
    ),
    ClientFeature(
        ui_key="compliance_schedule_fra_ocr_risk",
        settings_attr="compliance_schedule_fra_ocr_risk_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="compliance_schedule:update",
        reason=(
            "Gates the optional risk proposal block on the FRA OCR confirm sheet. "
            "Server refuses to create a risk without operator-entered likelihood/impact "
            "even when this is on; OCR ratings alone never open a risk row."
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
    ClientFeature(
        ui_key="document_graph",
        settings_attr="document_graph_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Doc Graph UI surfaces and /api/v1/document-graph. Default off (ADR-0021); "
            "API will 404 when closed so the flag discloses only that the module exists."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_heuristic_propose",
        settings_attr="document_graph_heuristic_propose_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates non-LLM Doc Graph edge proposals. Default off; propose→confirm only — "
            "never auto-confirms impact-driving edges (ADR-0021)."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_impact_propagation",
        settings_attr="document_graph_impact_propagation_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates publish-time Doc Graph impact assessments. Separate from the master graph "
            "flag so edges can ship before impact propagation opens (ADR-0021)."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_llm_propose",
        settings_attr="document_graph_llm_propose_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates LLM Doc Graph edge proposals. Default off and DPIA-gated later; AI may "
            "propose only — never auto-confirm impact-driving edges (ADR-0021)."
        ),
    ),
    # X-0 programme flags — registered default-off so later slices do not thrash this file.
    ClientFeature(
        ui_key="document_graph_thread_ambient",
        settings_attr="document_graph_thread_ambient_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates ambient Doc Graph thread UI on Document Detail. Default off; API thread "
            "walk remains behind master document_graph (ADR-0021 X-0)."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_map_view",
        settings_attr="document_graph_map_view_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Doc Graph map visualisation UI. Default off; pre-registered for later "
            "map-view slices without thrashing the catalogue (ADR-0021)."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_dnd_propose",
        settings_attr="document_graph_dnd_propose_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates drag-and-drop Doc Graph edge proposals. Default off; proposals only — "
            "never auto-confirm impact-driving edges (ADR-0021)."
        ),
    ),
    ClientFeature(
        ui_key="document_graph_structure_map",
        settings_attr="document_graph_structure_map_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Doc Graph structure-map surfaces. Default off; pre-registered for later "
            "structure-map slices (ADR-0021)."
        ),
    ),
    ClientFeature(
        ui_key="graph_coach",
        settings_attr="graph_coach_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Graph Coach guidance UX. Default off; pre-registered so later coach "
            "slices do not thrash the client feature catalogue."
        ),
    ),
    ClientFeature(
        ui_key="entity_360",
        settings_attr="entity_360_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Entity 360 composer + Connections strip + ImpactBundle. Default off; "
            "wired in X-1 — enable via deploy vars when baking."
        ),
    ),
    ClientFeature(
        ui_key="entity_360_satellites",
        settings_attr="entity_360_satellites_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Entity 360 satellite panels. Default off; pre-registered so satellite "
            "slices do not thrash the catalogue."
        ),
    ),
    ClientFeature(
        ui_key="job_lifecycle",
        settings_attr="job_lifecycle_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="job:read",
        reason=(
            "Gates Job Lifecycle axes API + surfaces (JL-1). Default off; "
            "enable via deploy vars when baking — ADR-0022 process vocab."
        ),
    ),
    ClientFeature(
        ui_key="job_cell_links",
        settings_attr="job_cell_links_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="document:read",
        reason=(
            "Gates Job cell-link surfaces. Default off; pre-registered so later cell-link "
            "slices do not thrash the client feature catalogue."
        ),
    ),
    ClientFeature(
        ui_key="register_catalogue",
        settings_attr="register_catalogue_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission=None,
        reason=(
            "Gates the PEL-HSEQ-5062 Register of Registers hub at /registers. There is no "
            "API behind the page, so an ungated route would stay reachable after the nav "
            "entry disappeared — App.tsx therefore renders NotFound when this is off. Not "
            "permission-gated while the hub shows no record counts; a count would need a "
            "permission and per-destination gating. Default off; discloses only that this "
            "deployment opted the index in."
        ),
    ),
    # The copilot pair is registered so the panel can state what it actually is. It is
    # the only consumer that needs these: the surface is mounted by its own build-time
    # gate, and what these two decide is the wording, not the door.
    ClientFeature(
        ui_key="ai_copilot",
        settings_attr="ai_copilot_enabled",
        kill_switch_key="copilot_kill_switch",
        enabling_flag_key=None,
        required_permission=None,
        reason=(
            "Tells the copilot panel whether the API behind it is open, so it can say "
            "'unavailable' rather than offer a chat box that 404s. Borrows the "
            "copilot_kill_switch key rather than declaring ai_copilot_kill_switch: that "
            "row is the one require_copilot_enabled already reads, and a second name "
            "would let the panel and the endpoint disagree about being killed. Not "
            "permission-gated because no copilot permission token exists to fold — the "
            "routes require authentication and nothing finer — so a false here would "
            "hide the disclosure from every caller. Discloses only that this deployment "
            "opted the surface in, which its own 404s already reveal."
        ),
    ),
    ClientFeature(
        ui_key="ai_copilot_inference",
        settings_attr="ai_copilot_inference_enabled",
        kill_switch_key="copilot_kill_switch",
        enabling_flag_key=None,
        required_permission=None,
        requires_ui_key="ai_copilot",
        reason=(
            "Distinguishes the two things the copilot can be: a keyword simulator, or "
            "grounded answers phrased over server-computed register facts with citations. "
            "Without it the panel has to hardcode one of those claims and is wrong in the "
            "other environment. Shares copilot_kill_switch for the same reason the master "
            "flag does — it is the row copilot_inference_is_enabled itself consults — and "
            "requires ai_copilot because AI_COPILOT_INFERENCE_ENABLED is a second opener, "
            "not an independent one: on with the master off means no inference at all."
        ),
    ),
    ClientFeature(
        ui_key="customer_feedback_kinds",
        settings_attr="customer_feedback_kinds_enabled",
        kill_switch_key=None,
        enabling_flag_key=None,
        required_permission="complaint:create",
        reason=(
            "Gates the staff New Feedback kind selector and POST/PATCH of "
            "feedback_kind other than complaint. Default on (FB-PR5); "
            "CUSTOMER_FEEDBACK_KINDS_ENABLED=false still subtracts. The API "
            "422s other kinds when this is off, so the flag discloses only that this "
            "deployment opted the write path in."
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
