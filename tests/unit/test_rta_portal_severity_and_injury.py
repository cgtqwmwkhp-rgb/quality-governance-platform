"""Portal RTA intake must not invent injuries or fatalities nobody reported.

The portal posts a generic triage word (low/medium/high/critical) that measures
urgency. It used to be mapped straight onto RTASeverity, an injury-outcome scale,
so "critical" became FATAL. The RTA form only ever emits "critical" (vehicle not
drivable) or "high", which made every portal collision a fatality or a serious
injury and left damage_only unreachable.
"""

from src.api.routes.employee_portal import QuickReportCreate, build_rta_portal_fields
from src.domain.models.rta import RTASeverity
from src.domain.services.rta_severity import derive_portal_rta_severity, interpret_rta_injury_answer, read_reported_bool


def _rta_report(severity: str, submission: dict) -> QuickReportCreate:
    return QuickReportCreate(
        report_type="rta",
        title="Road Traffic Collision - rear-end - A14",
        description="Rear-ended while stationary on the slip road.",
        severity=severity,
        location="A14 westbound, junction 52 slip road, Ipswich",
        reporter_name="UX Super",
        reporter_email="ux@example.com",
        reporter_submission=submission,
    )


# --- The reproduction of RTA-2026-0002 -------------------------------------


def _rta_2026_0002_submission() -> dict:
    """The verbatim payload shape captured from staging for RTA-2026-0002."""
    return {
        "employee_name": "UX Super",
        "pe_vehicle": "ML23RRZ",
        "has_passengers": False,
        "location": "A14 westbound, junction 52 slip road, Ipswich",
        "accident_date": "2026-07-27",
        "accident_time": "08:15",
        "accident_type": "rear-end",
        "vehicle_count": 0,
        "third_parties": [],
        "third_party_injured": False,
        "impact_point": "rear",
        "damage_description": "Rear bumper crushed",
        "is_drivable": False,
        "road_condition": "wet",
        "has_witnesses": False,
        "emergency_services": "Police and Ambulance - driver conveyed to hospital",
        "police_ref": None,
        "photos": {"count": 0, "files": []},
    }


def test_undrivable_vehicle_is_not_recorded_as_a_fatality():
    """RTA-2026-0002: "the van cannot be driven" must not become "a person died"."""
    submission = _rta_2026_0002_submission()
    fields = build_rta_portal_fields(_rta_report("critical", submission), submission)

    assert fields["severity"] is not RTASeverity.FATAL
    assert fields["severity"] == RTASeverity.DAMAGE_ONLY


def test_drivability_survives_as_an_operational_fact_not_a_clinical_one():
    """The urgency signal moves to vehicle_drivable, which is where it belongs."""
    submission = _rta_2026_0002_submission()
    fields = build_rta_portal_fields(_rta_report("critical", submission), submission)

    assert fields["vehicle_drivable"] is False


def test_triage_word_never_selects_an_injury_outcome():
    """No triage word may produce an injury severity on its own."""
    submission = _rta_2026_0002_submission()
    for triage in ("low", "medium", "high", "critical"):
        fields = build_rta_portal_fields(_rta_report(triage, submission), submission)
        assert fields["severity"] == RTASeverity.DAMAGE_ONLY, triage
        assert fields["driver_injured"] is False, triage


def test_reported_driver_injury_is_recorded_and_raises_severity():
    submission = _rta_2026_0002_submission()
    submission["driver_injured"] = True
    submission["driver_injury_details"] = "Neck and lower back pain; conveyed to hospital."

    fields = build_rta_portal_fields(_rta_report("high", submission), submission)

    assert fields["driver_injured"] is True
    assert fields["severity"] == RTASeverity.MINOR_INJURY
    assert fields["driver_injury_details"] == "Neck and lower back pain; conveyed to hospital."


def test_reported_third_party_injury_still_raises_severity():
    submission = _rta_2026_0002_submission()
    submission["third_party_injured"] = True
    submission["third_parties"] = [{"vehicle_reg": "AB12 CDE", "injured": True}]

    fields = build_rta_portal_fields(_rta_report("high", submission), submission)

    assert fields["third_party_injured"] is True
    assert fields["severity"] == RTASeverity.MINOR_INJURY


def test_intake_never_asserts_fatal_or_serious_injury_for_any_input():
    """Grading an injury is a staff determination made after assessment."""
    for driver, third_party in (
        (True, True),
        (True, False),
        (False, True),
        (None, None),
    ):
        severity = derive_portal_rta_severity(driver_injured=driver, third_party_injured=third_party)
        assert severity not in (RTASeverity.FATAL, RTASeverity.SERIOUS_INJURY)


# --- Tri-state injury answers (the latent #1412 class on the RTA path) ------


def test_string_no_is_not_read_as_an_injury():
    """bool("no") is True; #1412 fixed this on the incident path."""
    assert interpret_rta_injury_answer("no") is False
    assert interpret_rta_injury_answer("No") is False
    assert interpret_rta_injury_answer("false") is False
    assert interpret_rta_injury_answer("0") is False


def test_string_yes_is_read_as_an_injury():
    assert interpret_rta_injury_answer("yes") is True
    assert interpret_rta_injury_answer("true") is True
    assert interpret_rta_injury_answer("1") is True


def test_unanswered_is_unknown_not_no():
    """A question nobody asked is not an answer of "no"."""
    assert interpret_rta_injury_answer(None) is None
    assert interpret_rta_injury_answer("") is None
    assert interpret_rta_injury_answer("   ") is None
    assert interpret_rta_injury_answer([]) is None


def test_unrecognised_answer_fails_towards_injury():
    """An answer nobody anticipated must not silently downgrade an injury."""
    assert interpret_rta_injury_answer("maybe") is True
    assert interpret_rta_injury_answer("taken to hospital") is True
    assert interpret_rta_injury_answer([{"body_part": "neck"}]) is True


def test_real_booleans_pass_through():
    assert interpret_rta_injury_answer(True) is True
    assert interpret_rta_injury_answer(False) is False


def test_string_no_from_a_future_template_does_not_forge_a_third_party_injury():
    """A template revision posting strings must not flip third_party_injured."""
    submission = _rta_2026_0002_submission()
    submission["third_party_injured"] = "no"
    submission["third_parties"] = [{"vehicle_reg": "AB12 CDE"}]

    fields = build_rta_portal_fields(_rta_report("high", submission), submission)

    assert fields["third_party_injured"] is False
    assert fields["severity"] == RTASeverity.DAMAGE_ONLY


def test_string_no_from_a_future_template_does_not_forge_a_driver_injury():
    submission = _rta_2026_0002_submission()
    submission["driver_injured"] = "no"

    fields = build_rta_portal_fields(_rta_report("critical", submission), submission)

    assert fields["driver_injured"] is False
    assert fields["severity"] == RTASeverity.DAMAGE_ONLY


def test_non_string_injury_details_are_dropped_not_passed_to_a_text_column():
    """reporter_submission is arbitrary client JSON and must not reach the DB raw."""
    submission = _rta_2026_0002_submission()
    submission["driver_injured"] = True
    submission["driver_injury_details"] = {"unexpected": "structure"}

    fields = build_rta_portal_fields(_rta_report("high", submission), submission)

    assert fields["driver_injury_details"] is None
    assert fields["driver_injured"] is True


def test_whitespace_injury_details_are_normalised_to_null():
    submission = _rta_2026_0002_submission()
    submission["driver_injured"] = True
    submission["driver_injury_details"] = "   "

    fields = build_rta_portal_fields(_rta_report("high", submission), submission)

    assert fields["driver_injury_details"] is None


def test_drivability_only_accepts_a_real_boolean():
    """No safe direction to guess in: an unparseable answer stays unknown."""
    assert read_reported_bool(True) is True
    assert read_reported_bool(False) is False
    assert read_reported_bool(None) is None
    assert read_reported_bool("no") is None
    assert read_reported_bool("") is None
