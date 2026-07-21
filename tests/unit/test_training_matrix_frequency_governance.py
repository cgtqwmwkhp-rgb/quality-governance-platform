"""Unit tests for frequency-matrix dual-control gates."""

from types import SimpleNamespace

import pytest

from src.api.routes.training_matrix import (
    FREQUENCY_MATRIX_APPROVER_EMAIL,
    _is_frequency_approver,
    _require_frequency_approver,
)
from src.domain.exceptions import AuthorizationError


def test_frequency_approver_matches_david_harris_email():
    user = SimpleNamespace(email=FREQUENCY_MATRIX_APPROVER_EMAIL, is_superuser=False)
    assert _is_frequency_approver(user) is True


def test_frequency_approver_is_case_insensitive():
    user = SimpleNamespace(email="David.Harris@Plantexpand.com", is_superuser=False)
    assert _is_frequency_approver(user) is True


def test_frequency_approver_allows_superuser():
    user = SimpleNamespace(email="other@example.com", is_superuser=True)
    assert _is_frequency_approver(user) is True


def test_frequency_approver_rejects_other_admins():
    user = SimpleNamespace(email="admin@example.com", is_superuser=False)
    assert _is_frequency_approver(user) is False
    with pytest.raises(AuthorizationError):
        _require_frequency_approver(user)
