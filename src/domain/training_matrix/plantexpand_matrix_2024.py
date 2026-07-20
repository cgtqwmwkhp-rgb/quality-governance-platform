"""April 2024 (v1) Plantexpand Training Matrix — seed template only.

This is a one-shot SoR seed for Admin → Requirements. Compliance always reads
from training_matrix_requirements rows; admins may edit/delete after seeding.
"""

from __future__ import annotations

from typing import Final, TypedDict

TEMPLATE_ID: Final = "plantexpand_2024_v1"
TEMPLATE_LABEL: Final = "Plantexpand Training Matrix (2024) — April 2024 (v1)"

# PDF role columns → department match strings (substring match against Atlas dept).
ROLES: Final[tuple[str, ...]] = ("Engineer", "Workshop", "Office", "Management")


class MatrixModule(TypedDict):
    module: str
    roles: tuple[str, ...]
    frequency_years: int


class SeedRow(TypedDict):
    match_department: str
    match_role_key: None
    module: str
    frequency_years: int
    template_id: str


# Source: Plantexpand Training Matrix (2024).pdf — X marks required roles.
PLANTEXPAND_MATRIX_2024: Final[tuple[MatrixModule, ...]] = (
    {"module": "Appraisals", "roles": ("Management",), "frequency_years": 3},
    {"module": "Asbestos Awareness", "roles": ("Engineer", "Workshop"), "frequency_years": 1},
    {"module": "Atlas for managers", "roles": ("Management",), "frequency_years": 3},
    {
        "module": "Bullying & Harassment (Employees)",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 2,
    },
    {
        "module": "Bullying & Harassment (Managers & Employers)",
        "roles": ("Management",),
        "frequency_years": 2,
    },
    {
        "module": "COSHH Awareness",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 2,
    },
    {
        "module": "CPR Awareness / First Aid",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {"module": "Driving At Work", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {"module": "DSE", "roles": ("Office", "Management"), "frequency_years": 1},
    {
        "module": "Environmental Awareness",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 3,
    },
    {
        "module": "Environmental Awareness for Managers",
        "roles": ("Management",),
        "frequency_years": 3,
    },
    {
        "module": "Equality Act",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 3,
    },
    {
        "module": "Fire Extinguisher use",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {
        "module": "Fire Safety Awareness",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {
        "module": "GDPR",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {
        "module": "Hand Hygiene",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 3,
    },
    {"module": "Hand Arm Vibration", "roles": ("Engineer", "Workshop"), "frequency_years": 2},
    {
        "module": "Health and Safety Awareness",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {
        "module": "Information Security",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {"module": "Ladders and stepladders", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {"module": "Legionella / Legionnaires", "roles": ("Engineer", "Workshop"), "frequency_years": 2},
    {"module": "Lone Working", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {"module": "Manual Handling", "roles": ("Engineer", "Workshop"), "frequency_years": 1},
    {
        "module": "Manual Handling for low risk environments",
        "roles": ("Office", "Management"),
        "frequency_years": 1,
    },
    {
        "module": "Modern Slavery",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 3,
    },
    {
        "module": "PPE",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {"module": "Risk Assessment awareness", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {"module": "Return to Work Interviews", "roles": ("Management",), "frequency_years": 3},
    {
        "module": "Respiratory Protective Equipment (RPE) Awareness",
        "roles": ("Engineer", "Workshop"),
        "frequency_years": 1,
    },
    {"module": "RIDDOR", "roles": ("Management",), "frequency_years": 3},
    {"module": "Work Related Skin Diseases", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {
        "module": "Anti-Bribery",
        "roles": ("Engineer", "Workshop", "Office", "Management"),
        "frequency_years": 3,
    },
    {"module": "Skin Disease", "roles": ("Engineer", "Workshop"), "frequency_years": 3},
    {"module": "Working at Height", "roles": ("Engineer", "Workshop"), "frequency_years": 1},
    {
        "module": "Young Persons in the workplace",
        "roles": ("Workshop", "Office", "Management"),
        "frequency_years": 1,
    },
    {"module": "Disciplinary", "roles": ("Management",), "frequency_years": 3},
)

# PDF / common spelling variants → preferred module label (for Atlas match hints).
MODULE_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "hand hygiene": ("hand hygeine", "hand hygene"),
    "legionella / legionnaires": ("legionella / legionaires", "legionella", "legionnaires"),
    "anti-bribery": ("anti - bribery", "anti bribery", "antibribery"),
    "cpr awareness / first aid": ("cpr awareness", "first aid", "cpr / first aid"),
    "respiratory protective equipment (rpe) awareness": (
        "rpe awareness",
        "respiratory protective equipment awareness",
    ),
    "bullying & harassment (employees)": ("bullying and harassment (employees)",),
    "bullying & harassment (managers & employers)": (
        "bullying and harassment (managers & employers)",
        "bullying & harassment (managers and employers)",
    ),
}


def expand_seed_rows() -> list[SeedRow]:
    """Expand matrix modules × roles into requirement seed rows."""
    rows: list[SeedRow] = []
    for item in PLANTEXPAND_MATRIX_2024:
        for role in item["roles"]:
            rows.append(
                {
                    "match_department": role,
                    "match_role_key": None,
                    "module": item["module"],
                    "frequency_years": item["frequency_years"],
                    "template_id": TEMPLATE_ID,
                }
            )
    return rows
