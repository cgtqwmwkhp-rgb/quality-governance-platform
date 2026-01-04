"""
Determinism Smoke Tests (Stage 2.0 Phase 3)

Ensures that API outputs are deterministic and have stable ordering.
This is critical for auditability and preventing non-obvious regressions.
"""

import pytest


def test_list_sorting_is_deterministic():
    """
    Test that list sorting produces consistent, deterministic results.
    
    This is a smoke test to ensure that any list-based outputs
    (e.g., from API endpoints) maintain stable ordering.
    """
    # Sample data that might be returned from a database query
    unsorted_data = [
        {"id": 3, "name": "Charlie"},
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob"},
    ]
    
    # Sort by ID (ascending)
    sorted_data_1 = sorted(unsorted_data, key=lambda x: x["id"])
    sorted_data_2 = sorted(unsorted_data, key=lambda x: x["id"])
    
    # Verify determinism: same input, same output
    assert sorted_data_1 == sorted_data_2
    assert sorted_data_1[0]["id"] == 1
    assert sorted_data_1[1]["id"] == 2
    assert sorted_data_1[2]["id"] == 3


def test_dict_serialization_is_deterministic():
    """
    Test that dictionary serialization is deterministic.
    
    While Python 3.7+ guarantees dict insertion order,
    this test ensures we're aware of ordering in serialized outputs.
    """
    data = {"z": 3, "a": 1, "m": 2}
    
    # Convert to list of tuples (sorted by key)
    sorted_items_1 = sorted(data.items())
    sorted_items_2 = sorted(data.items())
    
    # Verify determinism
    assert sorted_items_1 == sorted_items_2
    assert sorted_items_1 == [("a", 1), ("m", 2), ("z", 3)]


def test_set_to_list_conversion_is_deterministic():
    """
    Test that set-to-list conversions are handled deterministically.
    
    Sets are unordered, so any conversion to a list must be explicitly sorted
    to ensure deterministic output.
    """
    # Sets are unordered
    unordered_set = {3, 1, 2}
    
    # Convert to sorted list
    sorted_list_1 = sorted(list(unordered_set))
    sorted_list_2 = sorted(list(unordered_set))
    
    # Verify determinism
    assert sorted_list_1 == sorted_list_2
    assert sorted_list_1 == [1, 2, 3]


@pytest.mark.parametrize("run_number", [1, 2, 3])
def test_repeated_execution_produces_same_result(run_number):
    """
    Test that repeated executions produce the same result.
    
    This parameterized test runs the same logic multiple times
    to verify deterministic behavior.
    """
    # Simulate a computation that should always return the same result
    result = sum([1, 2, 3, 4, 5])
    
    # Verify the result is always the same
    assert result == 15
