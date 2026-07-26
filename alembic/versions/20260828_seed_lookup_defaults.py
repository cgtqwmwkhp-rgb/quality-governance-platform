"""Seed UK lookup defaults for empty tenant categories (Run021 GROUP 1).

Revision ID: 20260828_lookup_defaults
Revises: 20260827_lookup_tenant_fix
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "20260828_lookup_defaults"
down_revision: Union[str, Sequence[str], None] = "20260827_lookup_tenant_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared with src/domain/services/lookup_defaults_seed_data.py — kept inline so the
# migration stays self-contained if the module moves later.
_DEFAULT_ROWS: tuple[tuple[str, str, str, int], ...] = (
    ("workforce_roles", "workshop_engineer", "Workshop Engineer / Technician", 1),
    ("workforce_roles", "mobile_fitter", "Mobile Fitter (Fleet Mobile Team)", 2),
    ("workforce_roles", "field_engineer", "Field Engineer", 3),
    ("workforce_roles", "ev_technician", "EV Technician (Electric Vehicle Centre)", 4),
    ("workforce_roles", "apprentice", "Apprentice", 5),
    ("workforce_roles", "workshop_controller", "Workshop Controller", 6),
    ("workforce_roles", "service_desk", "Service Desk / Scheduler", 7),
    ("workforce_roles", "supervisor", "Supervisor", 8),
    ("workforce_roles", "fleet_manager", "Fleet / Asset Manager", 9),
    ("workforce_roles", "hs_advisor", "Health & Safety Advisor", 10),
    ("workforce_roles", "compliance_admin", "Compliance / Administration", 11),
    ("workforce_roles", "driver", "Driver", 12),
    ("workforce_roles", "director", "Director", 13),
    ("workforce_roles", "subcontractor", "Subcontractor", 14),
    ("workforce_roles", "customer_staff", "Customer staff", 15),
    ("workforce_roles", "visitor", "Visitor / Member of the public", 16),
    ("workforce_roles", "other", "Other", 17),
    ("severity_levels", "critical", "Critical", 1),
    ("severity_levels", "high", "High", 2),
    ("severity_levels", "medium", "Medium", 3),
    ("severity_levels", "low", "Low", 4),
    ("severity_levels", "negligible", "Negligible", 5),
    ("incident_types", "injury", "Injury / accident", 1),
    ("incident_types", "ill_health", "Occupational ill health", 2),
    ("incident_types", "dangerous_occurrence", "Dangerous occurrence (RIDDOR Schedule 2)", 3),
    ("incident_types", "hazard", "Hazard / unsafe condition", 4),
    ("incident_types", "property_damage", "Property or asset damage", 5),
    ("incident_types", "vehicle_incident", "Vehicle incident", 6),
    ("incident_types", "environmental", "Environmental (spill, leak, emission)", 7),
    ("incident_types", "fire", "Fire or explosion", 8),
    ("incident_types", "utility_strike", "Utility strike / service damage", 9),
    ("incident_types", "security", "Security, theft or violence", 10),
    ("incident_types", "quality", "Quality or service failure", 11),
    ("incident_types", "other", "Other", 12),
    ("complaint_types", "workmanship", "Workmanship / repair defect", 1),
    ("complaint_types", "service_quality", "Service quality", 2),
    ("complaint_types", "delay", "Delay or missed SLA", 3),
    ("complaint_types", "damage", "Damage to customer property", 4),
    ("complaint_types", "billing", "Billing or invoicing", 5),
    ("complaint_types", "conduct", "Staff conduct or behaviour", 6),
    ("complaint_types", "communication", "Communication or updates", 7),
    ("complaint_types", "hse_concern", "Health, safety or environmental concern", 8),
    ("complaint_types", "vehicle_standard", "Vehicle or plant standard", 9),
    ("complaint_types", "other", "Other", 10),
    ("medical_assistance", "none", "None required", 1),
    ("medical_assistance", "self_administered", "Self-administered first aid", 2),
    ("medical_assistance", "first_aider", "Treated by a qualified first aider on site", 3),
    ("medical_assistance", "gp", "GP or walk-in centre", 4),
    ("medical_assistance", "minor_injuries", "Minor injuries unit", 5),
    ("medical_assistance", "ae", "A&E attendance", 6),
    ("medical_assistance", "ambulance_treated", "Treated by ambulance crew, not conveyed", 7),
    ("medical_assistance", "hospital_admission", "Hospital admission — RIDDOR check required", 8),
    ("medical_assistance", "occupational_health", "Occupational health referral", 9),
    ("medical_assistance", "declined", "Treatment offered and declined", 10),
    ("emergency_services", "none", "None called", 1),
    ("emergency_services", "ambulance", "Ambulance", 2),
    ("emergency_services", "fire_rescue", "Fire and Rescue Service", 3),
    ("emergency_services", "police", "Police", 4),
    ("emergency_services", "hart", "Hazardous Area Response Team", 5),
    ("emergency_services", "national_highways", "National Highways / Traffic Officers", 6),
    ("emergency_services", "utility_emergency", "Utility emergency response (gas, electricity, water)", 7),
    ("emergency_services", "coastguard", "Coastguard", 8),
    ("emergency_services", "multiple", "Multiple services attended", 9),
)


def upgrade() -> None:
    for category, code, label, display_order in _DEFAULT_ROWS:
        op.execute(
            f"""
            INSERT INTO lookup_options (
                tenant_id, category, code, label, is_active, display_order, created_at, updated_at
            )
            SELECT
                t.id,
                '{category}',
                '{code}',
                '{label.replace("'", "''")}',
                true,
                {display_order},
                NOW(),
                NOW()
            FROM tenants t
            WHERE NOT EXISTS (
                SELECT 1 FROM lookup_options l
                WHERE l.tenant_id = t.id AND l.category = '{category}'
            )
            AND NOT EXISTS (
                SELECT 1 FROM lookup_options l2
                WHERE l2.tenant_id = t.id
                  AND l2.category = '{category}'
                  AND l2.code = '{code}'
            )
            """
        )


def downgrade() -> None:
    # Non-destructive: leave seeded rows in place so admin edits are preserved.
    pass
