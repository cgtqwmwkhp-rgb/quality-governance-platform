"""Unit tests for form publish validation (Run021 PX-121)."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from src.domain.exceptions import ValidationError
from src.domain.services.form_publish_validation import (
    collect_required_lookup_categories,
    resolve_lookup_category,
    validate_form_template_publishable,
)


@dataclass
class Field:
    name: str
    label: str
    field_type: str
    is_required: bool = False
    options: list | None = None


@dataclass
class Step:
    fields: list[Field] = field(default_factory=list)


@dataclass
class Template:
    name: str
    steps: list[Step] = field(default_factory=list)


def test_resolve_lookup_category_ignores_free_text_role_fields():
    assert resolve_lookup_category(Field("complainant_role", "Role / Title", "text")) is None


def test_collect_required_lookup_categories_for_incident():
    template = Template(
        name="Incident",
        steps=[
            Step(
                fields=[
                    Field("contract", "Customer", "select", is_required=True),
                    Field("person_role", "Role", "select", is_required=True),
                ]
            )
        ],
    )
    assert collect_required_lookup_categories(template) == {
        "customers": ["Customer"],
        "workforce_roles": ["Role"],
    }


def test_validate_form_template_publishable_rejects_empty_workforce_roles():
    template = Template(
        name="Incident",
        steps=[Step(fields=[Field("person_role", "Role", "select", is_required=True)])],
    )
    with pytest.raises(ValidationError, match="Workforce Roles"):
        validate_form_template_publishable(template, {"workforce_roles": 0})


def test_validate_form_template_publishable_allows_configured_lookups():
    template = Template(
        name="Incident",
        steps=[
            Step(
                fields=[
                    Field("contract", "Customer", "select", is_required=True),
                    Field("person_role", "Role", "select", is_required=True),
                ]
            )
        ],
    )
    validate_form_template_publishable(
        template,
        {"customers": 2, "workforce_roles": 5},
    )


def test_validate_form_template_publishable_allows_inline_select_options():
    template = Template(
        name="Toggle form",
        steps=[
            Step(
                fields=[
                    Field(
                        "was_involved",
                        "Involved?",
                        "toggle",
                        is_required=True,
                        options=[{"value": "yes", "label": "Yes"}],
                    )
                ]
            )
        ],
    )
    validate_form_template_publishable(template, {})
