"""Every retention rule must name something real, and honour the declared policy.

Four separate defects lived in `RETENTION_RULES` simultaneously, and every one of them
was invisible without a live PostgreSQL run:

  * `notification_log` -- table does not exist (it is `notification_logs`), so the
    90-day push-log retention never deleted a row.
  * `audit_log_entries.created_at` -- column does not exist (it is `timestamp`). This
    rule ran *first*, aborting the shared transaction and silently degrading the
    closing COMMIT to a rollback, so no later rule purged anything either.
  * `investigations` -- no such table.
  * `incidents`/`complaints`/`near_misses` at 365 days, against a declared 2555/2555/1825.
    A hard DELETE at a seventh of the statutory period, cascading to child rows.

A misnamed target fails loudly here rather than at 02:00 in a swallowed exception, and a
horizon cannot disagree with the policy because it is no longer written twice.

Where the schema checks live
---------------------------
Deliberately not here. Whether every rule names a real table and a real column is asserted
in ``tests/unit/infrastructure/test_data_retention_targets.py``, which reads the schema in
a *child interpreter*. That matters: importing every model module in-process registers
tables on the shared ``Base.metadata``, and doing so makes
``test_delete_cascade_audit_visibility`` fail with two workflow cascades its register does
not carry -- purely because this module ran first. Measured, not assumed: an earlier draft
of this file did exactly that and broke it. So this module restricts itself to properties
that need no schema at all, and does not duplicate the two that do.
"""

from __future__ import annotations

import pytest

from src.core.retention_config import DEFAULT_RETENTION_POLICIES
from src.infrastructure.tasks.cleanup_tasks import RETENTION_RULES, RetentionRule


def _ids(rule: RetentionRule) -> str:
    return rule.table


@pytest.mark.parametrize("rule", RETENTION_RULES, ids=_ids)
def test_the_horizon_comes_from_the_policy_when_one_governs(rule: RetentionRule) -> None:
    """A governed table's horizon must be the policy's, not a copy of it."""
    if rule.policy_key is None:
        pytest.skip(f"{rule.table} is operational, not governed by a retention policy")
    assert rule.retention_days == DEFAULT_RETENTION_POLICIES[rule.policy_key].retention_days


@pytest.mark.parametrize("rule", RETENTION_RULES, ids=_ids)
def test_nothing_soft_delete_first_is_hard_deleted(rule: RetentionRule) -> None:
    """The guard that stops this sweep destroying statutory records.

    This is the load-bearing assertion. The sweep runs unattended at 02:00 and the
    deletes cascade, so a table whose policy says "withdraw before destroying" must not
    be reachable by a bare DELETE.
    """
    if rule.policy_key is None:
        return
    if DEFAULT_RETENTION_POLICIES[rule.policy_key].soft_delete_first:
        assert not rule.may_hard_delete, (
            f"{rule.table} is governed by {rule.policy_key}, which requires soft delete "
            "first, yet this sweep would issue a hard DELETE."
        )


def test_a_rule_cannot_invent_its_own_horizon() -> None:
    """Supplying both sources, or neither, is refused at construction."""
    with pytest.raises(ValueError, match="exactly one"):
        RetentionRule("incidents", "created_at", policy_key="incidents", operational_days=365)
    with pytest.raises(ValueError, match="exactly one"):
        RetentionRule("incidents", "created_at")


def test_a_rule_cannot_name_a_policy_that_does_not_exist() -> None:
    with pytest.raises(ValueError, match="unknown retention policy"):
        RetentionRule("road_traffic_collisions", "created_at", policy_key="road_traffic_collisions")


def test_the_sweep_would_purge_only_ungoverned_operational_tables() -> None:
    """Pin the current effective blast radius, so widening it is a visible decision.

    Not a statement that this set is the final answer -- it is a statement that changing
    it should require editing this list and saying why.
    """
    purgeable = {rule.table for rule in RETENTION_RULES if rule.may_hard_delete}
    assert purgeable == {"token_blacklist", "notification_logs"}
