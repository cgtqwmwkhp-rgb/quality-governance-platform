"""UK Plantexpand lookup defaults for unconfigured environments (Run021 GROUP 1).

Values align with ``04-reference/QGP-Lookup-Configuration-Values.md`` so admin
and portal channels stay compatible. Customers are intentionally excluded —
those are contract-specific business data.

``complaint_types`` and ``incident_types`` are not free-form: their codes are
submitted verbatim as enum-validated API fields, so every code has to be a
member of the matching enum. See ``lookup_enum_contract`` for why, and
``tests/integration/test_lookup_enum_contract.py`` for the test that holds the
two halves together.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LookupDefaultRow:
    category: str
    code: str
    label: str
    display_order: int


# Categories seeded when a tenant has no rows in that category.
SEED_CATEGORIES: tuple[str, ...] = (
    "workforce_roles",
    "severity_levels",
    "incident_types",
    "complaint_types",
    "medical_assistance",
    "emergency_services",
)

LOOKUP_DEFAULT_ROWS: tuple[LookupDefaultRow, ...] = (
    # 1. Workforce Roles — unblocks portal incident intake (PX-119)
    LookupDefaultRow("workforce_roles", "workshop_engineer", "Workshop Engineer / Technician", 1),
    LookupDefaultRow("workforce_roles", "mobile_fitter", "Mobile Fitter (Fleet Mobile Team)", 2),
    LookupDefaultRow("workforce_roles", "field_engineer", "Field Engineer", 3),
    LookupDefaultRow("workforce_roles", "ev_technician", "EV Technician (Electric Vehicle Centre)", 4),
    LookupDefaultRow("workforce_roles", "apprentice", "Apprentice", 5),
    LookupDefaultRow("workforce_roles", "workshop_controller", "Workshop Controller", 6),
    LookupDefaultRow("workforce_roles", "service_desk", "Service Desk / Scheduler", 7),
    LookupDefaultRow("workforce_roles", "supervisor", "Supervisor", 8),
    LookupDefaultRow("workforce_roles", "fleet_manager", "Fleet / Asset Manager", 9),
    LookupDefaultRow("workforce_roles", "hs_advisor", "Health & Safety Advisor", 10),
    LookupDefaultRow("workforce_roles", "compliance_admin", "Compliance / Administration", 11),
    LookupDefaultRow("workforce_roles", "driver", "Driver", 12),
    LookupDefaultRow("workforce_roles", "director", "Director", 13),
    LookupDefaultRow("workforce_roles", "subcontractor", "Subcontractor", 14),
    LookupDefaultRow("workforce_roles", "customer_staff", "Customer staff", 15),
    LookupDefaultRow("workforce_roles", "visitor", "Visitor / Member of the public", 16),
    LookupDefaultRow("workforce_roles", "other", "Other", 17),
    # 2. Severity Levels — matches hardcoded admin modal (PX-131 compatibility)
    LookupDefaultRow("severity_levels", "critical", "Critical", 1),
    LookupDefaultRow("severity_levels", "high", "High", 2),
    LookupDefaultRow("severity_levels", "medium", "Medium", 3),
    LookupDefaultRow("severity_levels", "low", "Low", 4),
    LookupDefaultRow("severity_levels", "negligible", "Negligible", 5),
    # 3. Incident Types — codes are ``IncidentType`` members (R22-01). The label
    # carries the UK construction and utilities wording; the code is what the
    # form submits as ``incident_type``, so it cannot be anything else.
    LookupDefaultRow("incident_types", "injury", "Injury / accident", 1),
    LookupDefaultRow("incident_types", "near_miss", "Near miss / close call", 2),
    LookupDefaultRow("incident_types", "hazard", "Hazard / unsafe condition", 3),
    LookupDefaultRow("incident_types", "property_damage", "Property, plant or vehicle damage", 4),
    LookupDefaultRow("incident_types", "environmental", "Environmental (spill, leak, emission)", 5),
    LookupDefaultRow("incident_types", "security", "Security, theft or violence", 6),
    LookupDefaultRow("incident_types", "quality", "Quality or service failure", 7),
    LookupDefaultRow("incident_types", "other", "Other", 8),
    # 4. Complaint Types — codes are ``ComplaintType`` members (PX-281/282).
    LookupDefaultRow("complaint_types", "service", "Service or workmanship", 1),
    LookupDefaultRow("complaint_types", "product", "Product, plant or materials supplied", 2),
    LookupDefaultRow("complaint_types", "delivery", "Delivery, delay or missed appointment", 3),
    LookupDefaultRow("complaint_types", "communication", "Communication or updates", 4),
    LookupDefaultRow("complaint_types", "billing", "Billing or invoicing", 5),
    LookupDefaultRow("complaint_types", "staff", "Staff conduct or behaviour", 6),
    LookupDefaultRow("complaint_types", "safety", "Health and safety concern", 7),
    LookupDefaultRow("complaint_types", "environmental", "Environmental (noise, spill, waste)", 8),
    LookupDefaultRow("complaint_types", "other", "Other", 9),
    # 5. Medical Assistance
    LookupDefaultRow("medical_assistance", "none", "None required", 1),
    LookupDefaultRow("medical_assistance", "self_administered", "Self-administered first aid", 2),
    LookupDefaultRow("medical_assistance", "first_aider", "Treated by a qualified first aider on site", 3),
    LookupDefaultRow("medical_assistance", "gp", "GP or walk-in centre", 4),
    LookupDefaultRow("medical_assistance", "minor_injuries", "Minor injuries unit", 5),
    LookupDefaultRow("medical_assistance", "ae", "A&E attendance", 6),
    LookupDefaultRow("medical_assistance", "ambulance_treated", "Treated by ambulance crew, not conveyed", 7),
    LookupDefaultRow("medical_assistance", "hospital_admission", "Hospital admission — RIDDOR check required", 8),
    LookupDefaultRow("medical_assistance", "occupational_health", "Occupational health referral", 9),
    LookupDefaultRow("medical_assistance", "declined", "Treatment offered and declined", 10),
    # 6. Emergency Services
    LookupDefaultRow("emergency_services", "none", "None called", 1),
    LookupDefaultRow("emergency_services", "ambulance", "Ambulance", 2),
    LookupDefaultRow("emergency_services", "fire_rescue", "Fire and Rescue Service", 3),
    LookupDefaultRow("emergency_services", "police", "Police", 4),
    LookupDefaultRow("emergency_services", "hart", "Hazardous Area Response Team", 5),
    LookupDefaultRow("emergency_services", "national_highways", "National Highways / Traffic Officers", 6),
    LookupDefaultRow(
        "emergency_services", "utility_emergency", "Utility emergency response (gas, electricity, water)", 7
    ),
    LookupDefaultRow("emergency_services", "coastguard", "Coastguard", 8),
    LookupDefaultRow("emergency_services", "multiple", "Multiple services attended", 9),
)


def rows_for_category(category: str) -> tuple[LookupDefaultRow, ...]:
    return tuple(row for row in LOOKUP_DEFAULT_ROWS if row.category == category)
