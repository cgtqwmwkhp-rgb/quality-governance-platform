"""Publish-time validation for admin form templates (Run021 PX-121).

Blocks publishing when a required field is backed by a lookup catalog that has
no active options for the tenant — the condition that dead-ended portal intake.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, Sequence

from src.domain.exceptions import ValidationError

_LOOKUP_SELECT_TYPES = frozenset({"select", "multi_select"})

# Exact field name → lookup category (mirrors DynamicFormRenderer injection).
_EXACT_FIELD_LOOKUPS: dict[str, str] = {
    "person_role": "workforce_roles",
    "medical_assistance": "medical_assistance",
}

_LOOKUP_CATEGORY_LABELS: dict[str, str] = {
    "customers": "Customers",
    "workforce_roles": "Workforce Roles",
    "medical_assistance": "Medical Assistance",
}


class FormFieldLike(Protocol):
    name: str
    label: str
    field_type: str
    is_required: bool
    options: Any


class FormStepLike(Protocol):
    fields: Sequence[FormFieldLike]


class FormTemplateLike(Protocol):
    name: str
    steps: Sequence[FormStepLike]


def resolve_lookup_category(field: FormFieldLike) -> str | None:
    """Return the lookup category a field reads at runtime, if any."""
    field_type = (field.field_type or "").strip().lower()
    if field_type not in _LOOKUP_SELECT_TYPES:
        return None

    name = (field.name or "").strip().lower()
    if not name:
        return None

    if name in _EXACT_FIELD_LOOKUPS:
        return _EXACT_FIELD_LOOKUPS[name]

    if "customer" in name or "contract" in name:
        return "customers"

    # Free-text role fields (e.g. complainant_role) must not map to workforce_roles.
    if name.endswith("_role") or name == "role":
        return "workforce_roles"
    if "role" in name:
        return "workforce_roles"

    inline_options = field.options or []
    if isinstance(inline_options, list) and len(inline_options) > 0:
        return None

    return None


def collect_required_lookup_categories(template: FormTemplateLike) -> dict[str, list[str]]:
    """Map lookup category → field labels that require it."""
    required: dict[str, list[str]] = {}
    for step in template.steps or []:
        for field in step.fields or []:
            if not field.is_required:
                continue
            category = resolve_lookup_category(field)
            if not category:
                continue
            label = (field.label or field.name or "Unnamed field").strip()
            required.setdefault(category, []).append(label)
    return required


def validate_form_template_publishable(
    template: FormTemplateLike,
    lookup_counts: Mapping[str, int],
) -> None:
    """Raise ValidationError when a required lookup-backed field has no options."""
    if not (template.name or "").strip():
        raise ValidationError("Form name is required before publishing")

    if not template.steps:
        raise ValidationError("Form must have at least one step before publishing")

    has_field = any(step.fields for step in template.steps)
    if not has_field:
        raise ValidationError("Form must have at least one field before publishing")

    for category, field_labels in collect_required_lookup_categories(template).items():
        if lookup_counts.get(category, 0) > 0:
            continue
        lookup_label = _LOOKUP_CATEGORY_LABELS.get(category, category.replace("_", " ").title())
        fields_csv = ", ".join(field_labels)
        raise ValidationError(
            f"Cannot publish: required field(s) ({fields_csv}) use lookup '{lookup_label}' "
            f"but no active options are configured. Add values under Admin → Lookups → {lookup_label}."
        )
