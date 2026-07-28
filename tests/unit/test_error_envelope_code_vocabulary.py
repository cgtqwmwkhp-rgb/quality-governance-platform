"""The error envelope must carry the bare error-code vocabulary, not a Python name.

``ErrorCode`` is a ``(str, Enum)`` and ``Enum`` overrides ``__str__``, so
``str(ErrorCode.VALIDATION_ERROR)`` is ``"ErrorCode.VALIDATION_ERROR"`` rather
than ``"VALIDATION_ERROR"``. ``_normalize_http_detail`` used plain ``str()`` and
120 of the 121 ``api_error`` call sites pass a member, so every
``HTTPException`` raised with a structured detail leaked a qualified Python name.

Observed live on staging before the fix:

    {"error": {"code": "ErrorCode.CONFIGURATION_ERROR",
               "error_class": "ErrorCode.CONFIGURATION_ERROR", ...}}

Which of these fail on ``main``, stated honestly:

- ``TestNormalizeHttpDetail`` — the two enum cases **fail on main**. They are the
  regression tests proper.
- ``TestBuildEnvelope`` — the enum cases fail on main **only** on the
  ``type(...) is str`` assertion. Their value assertions pass unfixed, because a
  ``(str, Enum)`` member compares equal to its value and ``JSONResponse``
  serialises it as that value. So this path was **already correct on the wire**;
  these are guard tests pinning it against a future move to ``enum.StrEnum``, a
  change of JSON encoder, or someone reintroducing ``str()``. They are not
  evidence of a user-visible bug.

The tests exercise only ``_build_envelope`` and ``_normalize_http_detail``, both
of which exist unchanged on ``main``, so they fail on an assertion rather than on
an import when run against the unfixed code.
"""

from __future__ import annotations

import pytest

from src.api.middleware.error_handler import _build_envelope, _normalize_http_detail
from src.api.utils.errors import api_error
from src.domain.error_codes import ErrorCode


class TestNormalizeHttpDetail:
    def test_direct_payload_from_api_error_yields_bare_code(self):
        """The exact shape produced by api_error(ErrorCode.X, ...) — 120 call sites."""
        detail = api_error(ErrorCode.CONFIGURATION_ERROR, "Portal intake tenant is not configured.")
        code, message, _ = _normalize_http_detail(detail, 503)
        assert code == "CONFIGURATION_ERROR"
        assert message == "Portal intake tenant is not configured."

    def test_nested_envelope_payload_yields_bare_code(self):
        detail = {"error": {"code": ErrorCode.PERMISSION_DENIED, "message": "nope"}}
        code, _, _ = _normalize_http_detail(detail, 403)
        assert code == "PERMISSION_DENIED"

    def test_status_fallback_yields_bare_code(self):
        """An unstructured detail falls back to _STATUS_TO_ERROR_CODE, which holds enums."""
        code, _, _ = _normalize_http_detail("something went wrong", 404)
        assert code == "ENTITY_NOT_FOUND"

    def test_plain_string_code_is_unchanged(self):
        """Call sites that already pass a string must keep working."""
        code, _, _ = _normalize_http_detail({"code": "SETUP_REQUIRED", "message": "m"}, 400)
        assert code == "SETUP_REQUIRED"


class TestBuildEnvelope:
    """Guard tests. These pass on main — see the module docstring."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            (ErrorCode.INTERNAL_ERROR, "INTERNAL_ERROR"),
            (ErrorCode.VALIDATION_ERROR, "VALIDATION_ERROR"),
            ("SETUP_REQUIRED", "SETUP_REQUIRED"),
        ],
    )
    def test_envelope_code_and_alias_are_bare(self, code, expected):
        """Covers the two callers that bypass _normalize_http_detail entirely.

        The 500 and DomainError handlers pass an ErrorCode member straight in.
        Those were already correct on the wire; this pins it so it stays that way
        without depending on the JSON encoder's treatment of a str-Enum.
        """
        envelope = _build_envelope(code, "msg", "req-1")
        assert envelope["error"]["code"] == expected
        assert envelope["error"]["error_class"] == expected
        # The equality above also holds for a raw enum member, so assert the
        # stored object really is a plain str — that is what this fix changed.
        assert type(envelope["error"]["code"]) is str

    def test_code_and_error_class_stay_identical(self):
        """error_class is documented as a value-identical alias of code."""
        envelope = _build_envelope(ErrorCode.DUPLICATE_ENTITY, "msg", "req-1")
        assert envelope["error"]["code"] == envelope["error"]["error_class"]

    def test_no_member_of_the_vocabulary_leaks_a_python_name(self):
        """The whole regression in one assertion, across every code we define."""
        leaked = [
            member.name
            for member in ErrorCode
            if _build_envelope(member, "msg", "req-1")["error"]["code"] != member.value
        ]
        assert not leaked, f"{len(leaked)} error codes leak a qualified Python name: {leaked[:5]}"
