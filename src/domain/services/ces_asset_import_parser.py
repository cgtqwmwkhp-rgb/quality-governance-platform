"""Normalise CES Calibrations Equipment List workbook rows."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from src.domain.models.asset import AssetStatus

UK_VEHICLE_REG_PATTERN = re.compile(
    r"\b(?:[A-Z]{2}\d{2}\s?[A-Z]{3}|[A-Z]\d{1,3}\s?[A-Z]{3}|[A-Z]{3}\s?\d{1,3}[A-Z])\b",
    re.IGNORECASE,
)

# CES Location remainders often repeat the company brand after the ';' split
# ("Plantexpand Ltd ; Plantexpand Ltd Wickford"). Strip brand so site lookups
# store "Wickford" / "Workshop Hampton", never "Plantexpand …".
_BRAND_PREFIX_RE = re.compile(
    r"^(?:plantexpand(?:\s+limited|\s+ltd)?)\b[\s,.-]*",
    re.IGNORECASE,
)
_LEADING_LTD_RE = re.compile(r"^ltd\b[\s,.-]*", re.IGNORECASE)

CES_STATUS_MAP = {
    "fail": AssetStatus.QUARANTINED.value,
    "removed from service": AssetStatus.DECOMMISSIONED.value,
    "not made available": AssetStatus.ACTIVE.value,
}


def cell_text(value: Any) -> str:
    """Return a display-safe text representation of an XLSX cell."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value).strip()


def parse_ces_date(value: Any) -> datetime | None:
    if value is None or cell_text(value) == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = cell_text(value)
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
        else:
            raise ValueError(f"unrecognised date format: {raw!r}")
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def normalise_vehicle_reg(value: str) -> str | None:
    match = UK_VEHICLE_REG_PATTERN.search(value)
    if not match:
        return None
    return re.sub(r"\s+", "", match.group(0)).upper()


def strip_company_brand_prefix(text: str | None, company: str | None = None) -> str:
    """Remove leading Plantexpand / company brand tokens from a CES site label."""
    if not text:
        return ""
    result = re.sub(r"\s+", " ", str(text)).strip(" ,-")
    if company:
        company_norm = re.sub(r"\s+", " ", company).strip()
        if company_norm and result.lower().startswith(company_norm.lower()):
            result = result[len(company_norm) :].strip(" ,-")
    # Repeat for remainders like "Plantexpand Ltd Wickford" or "Plantexpand Workshop".
    while True:
        match = _BRAND_PREFIX_RE.match(result)
        if not match:
            break
        result = result[match.end() :].strip(" ,-")
    # After stripping "Plantexpand Ltd", a bare leading "Ltd" can remain.
    result = _LEADING_LTD_RE.sub("", result).strip(" ,-")
    return result


def split_location(value: Any) -> dict[str, str | None]:
    """Extract company, assignment text, vehicle registration and owner candidate."""
    raw = cell_text(value)
    parts = [part.strip() for part in raw.split(";") if part and part.strip()]
    company = parts[0] if parts else None
    remainder = " ; ".join(parts[1:]).strip() if len(parts) > 1 else ""
    vehicle_reg = normalise_vehicle_reg(remainder or raw)

    labelled_engineer = re.search(r"(?:engineer|technician)\s*[:\-]\s*([^;,(]+)", remainder, re.IGNORECASE)
    engineer_name = labelled_engineer.group(1).strip() if labelled_engineer else None
    assignment_text = remainder or company or ""
    if labelled_engineer:
        assignment_text = re.sub(
            r"(?:engineer|technician)\s*[:\-]\s*[^;,(]+",
            "",
            assignment_text,
            flags=re.IGNORECASE,
        ).strip(" ;,-")
    without_vehicle = UK_VEHICLE_REG_PATTERN.sub("", assignment_text).strip(" ,-()")
    if engineer_name is None and without_vehicle:
        # CES commonly stores unlabelled owners as
        # "Plantexpand Ltd ; Plantexpand Jane Smith" or after a vehicle reg.
        # Preserve known site labels such as "Workshop Ashford" as locations.
        company_words = (company or "").split()
        root = company_words[0] if company_words else ""
        candidate = re.sub(r"\s+", " ", without_vehicle).strip()
        has_implicit_engineer_prefix = False
        if company and candidate.lower().startswith(company.lower()):
            candidate = candidate[len(company) :].strip(" ,-")
            has_implicit_engineer_prefix = True
        elif root and candidate.lower().startswith(root.lower()):
            candidate = candidate[len(root) :].strip(" ,-")
            has_implicit_engineer_prefix = True
        site_prefixes = ("workshop", "spare", "uk power networks")
        if (
            has_implicit_engineer_prefix
            and re.fullmatch(r"[A-Za-zÀ-ÿ' -]{3,100}", candidate)
            and len(candidate.split()) >= 2
            and not candidate.lower().startswith(site_prefixes)
        ):
            engineer_name = candidate
            assignment_text = without_vehicle[: -len(candidate)].strip(" ,-")
        else:
            assignment_text = without_vehicle
    elif vehicle_reg:
        assignment_text = without_vehicle

    cleaned_assignment = strip_company_brand_prefix(assignment_text, company)
    return {
        "location_raw": raw,
        "company": company,
        "assignment_text": cleaned_assignment or None,
        "vehicle_reg": vehicle_reg,
        "engineer_name": engineer_name,
    }


def normalise_status(value: Any) -> tuple[str, bool]:
    raw = cell_text(value)
    key = re.sub(r"\s+", " ", raw).lower()
    if key.startswith("pass"):
        return AssetStatus.ACTIVE.value, False
    if key not in CES_STATUS_MAP:
        raise ValueError(f"unrecognised CES status: {raw!r}")
    return CES_STATUS_MAP[key], key == "not made available"


def normalise_ces_row(row: dict[str, Any]) -> dict[str, Any]:
    """Convert named Equipment List columns to the Asset import shape."""
    location = split_location(row.get("location"))
    equipment_type = cell_text(row.get("equipment_type"))
    make = cell_text(row.get("make")) or None
    model = cell_text(row.get("model")) or None
    capacity = cell_text(row.get("capacity")) or None
    name_parts = [equipment_type, make, model, capacity]
    status, not_made_available = normalise_status(row.get("status"))
    serial = cell_text(row.get("serial_number"))
    qr_code = cell_text(row.get("qr_code")) or None
    return {
        "__row__": row["__row__"],
        "equipment_type": equipment_type,
        "name": " — ".join(part for part in name_parts if part),
        "make": make,
        "model": model,
        "capacity": capacity,
        "serial_number": serial,
        "asset_id": cell_text(row.get("asset_id")) or None,
        "qr_code_data": qr_code,
        "last_inspection": parse_ces_date(row.get("last_inspection")),
        "expiry_date": parse_ces_date(row.get("next_inspection")),
        "status": status,
        "not_made_available": not_made_available,
        **location,
    }
