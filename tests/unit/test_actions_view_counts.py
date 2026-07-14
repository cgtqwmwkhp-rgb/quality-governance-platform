"""Unit tests for Actions view-counts badge helper wiring."""

from src.api.routes.actions import ActionsViewCountsResponse


def test_actions_view_counts_response_shape() -> None:
    body = ActionsViewCountsResponse(all=10, my=3, overdue=2, my_overdue=1)
    assert body.all == 10
    assert body.my == 3
    assert body.overdue == 2
    assert body.my_overdue == 1
    dumped = body.model_dump()
    assert set(dumped.keys()) == {"all", "my", "overdue", "my_overdue"}
