"""Unit tests for H&S Excel import parser routing and Y/N parsing."""

from datetime import datetime
from io import BytesIO

from openpyxl import Workbook

from src.domain.services.hs_excel_import_parser import (
    parse_hs_workbook,
    parse_yn,
    route_incident_log_type,
)


def test_parse_yn() -> None:
    assert parse_yn("Y") is True
    assert parse_yn("n") is False
    assert parse_yn("") is None


def test_route_incident_log_type() -> None:
    assert route_incident_log_type("Injury / Accident") == "incident"
    assert route_incident_log_type("Injury") == "incident"
    assert route_incident_log_type("Near Miss") == "near_miss"
    assert route_incident_log_type("Customer Complaint") == "complaint"
    assert route_incident_log_type("RTA") == "rta"


def _workbook_bytes() -> bytes:
    wb = Workbook()
    incident = wb.active
    incident.title = "Incident Log"
    incident.append(
        [
            "ID",
            "Date",
            "Reporting Year",
            "Reporter",
            "Customer / Contract",
            "Type",
            "Person Involved",
            "Role / Location",
            "Description",
            "Injury?",
            "Body Part",
            "Medical Assistance?",
            "RIDDOR?",
            "LTI?",
            "Minor Injury?",
            "HiPo Near Miss?",
            "Status",
            "Lessons Learnt / Notes",
        ]
    )
    incident.append(
        [
            1,
            datetime(2026, 1, 15),
            2026,
            "Jamie Uncle",
            "UKPN",
            "Injury / Accident",
            "John",
            "Mobile Engineer",
            "Cut finger",
            "Y",
            "Hands",
            "Y",
            "N",
            "N",
            "Y",
            "N",
            "Closed",
            "PPE reminder",
        ]
    )
    incident.append(
        [
            2,
            None,
            2026,
            "A",
            "",
            "Near Miss",
            "",
            "Office",
            "No date row",
            "N",
            "",
            "N",
            "N",
            "N",
            "N",
            "N",
            "Open",
            "",
        ]
    )
    incident.append(
        [
            3,
            datetime(2026, 2, 1),
            2026,
            "B",
            "",
            "Near Miss",
            "",
            "Workshop",
            "Slippery floor",
            "N",
            "",
            "N",
            "N",
            "N",
            "N",
            "N",
            "Open",
            "",
        ]
    )
    rta = wb.create_sheet("RTA Log")
    rta.append(
        [
            "ID",
            "Date",
            "Reporting Year",
            "Employee",
            "Vehicle Reg",
            "Time",
            "Location",
            "Accident Type",
            "Damage Description",
            "Drivable?",
            "Weather",
            "Road Conditions",
            "Emergency Services?",
            "Third-Party Injury?",
            "Employee Injured?",
            "LTI?",
            "RIDDOR?",
            "Notes",
        ]
    )
    rta.append(
        [
            10,
            datetime(2026, 3, 1),
            2026,
            "Driver",
            "AB12CDE",
            "10:00",
            "M25",
            "Rear-end collisions",
            "Bumper",
            "Y",
            "Dry",
            "Dry",
            "N",
            "N",
            "N",
            "N",
            "N",
            "",
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_hs_workbook_routes_and_skips_undated() -> None:
    parsed = parse_hs_workbook(_workbook_bytes())
    assert len(parsed["incident_log"]) == 2
    assert parsed["incident_log"][0]["module"] == "incident"
    assert parsed["incident_log"][0]["is_injury"] is True
    assert parsed["incident_log"][0]["body_part"] == "Hands"
    assert parsed["incident_log"][1]["module"] == "near_miss"
    assert len(parsed["rta_log"]) == 1
    assert parsed["rta_log"][0]["collision_type"] == "rear_end"
    assert any("no date" in w.lower() for w in parsed["warnings"])
