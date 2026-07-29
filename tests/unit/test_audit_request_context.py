"""PX-142b: the request-origin carrier must be absent off-request and never stale.

A ContextVar populated by middleware is right for request-scoped work, but the
two ways it goes wrong are worse than the null it replaces:

* raising, or requiring a request, would break every Celery task, beat schedule
  and startup hook that records an audit event;
* leaking a previous request's client address on a reused worker would put a
  false statement into a compliance record — an entry claiming an origin that
  belonged to somebody else's request.

These tests exercise both, plus concurrent tasks, because "it works in a single
request" is not evidence about either failure.
"""

from __future__ import annotations

import asyncio

import pytest

from src.domain.context.audit_request_context import (
    IP_ADDRESS_MAX_LENGTH,
    USER_AGENT_MAX_LENGTH,
    audit_request_context,
    build_audit_request_context,
    get_audit_request_context,
    reset_audit_request_context,
    set_audit_request_context,
)


def test_absent_outside_a_request_and_does_not_raise():
    """The Celery / startup / CLI case: absent, not an error."""
    context = get_audit_request_context()

    assert context.ip_address is None
    assert context.user_agent is None


def test_bound_values_are_visible_to_a_reader():
    with audit_request_context(ip_address="198.51.100.4", user_agent="probe/1"):
        context = get_audit_request_context()
        assert context.ip_address == "198.51.100.4"
        assert context.user_agent == "probe/1"


def test_context_is_absent_again_after_the_block_exits():
    with audit_request_context(ip_address="198.51.100.4", user_agent="probe/1"):
        pass

    assert get_audit_request_context().ip_address is None


def test_a_second_request_on_the_same_worker_does_not_inherit_the_first():
    """The stale-value failure mode, simulated as two sequential requests."""
    with audit_request_context(ip_address="10.0.0.1", user_agent="first"):
        assert get_audit_request_context().ip_address == "10.0.0.1"

    # Request two arrives with no forwarding header at all.
    with audit_request_context(ip_address=None, user_agent=None):
        leaked = get_audit_request_context()
        assert leaked.ip_address is None, f"request two inherited {leaked.ip_address!r} from request one"
        assert leaked.user_agent is None

    assert get_audit_request_context().ip_address is None


def test_an_exception_inside_the_block_still_unwinds_the_context():
    with pytest.raises(RuntimeError):
        with audit_request_context(ip_address="10.0.0.2", user_agent="boom"):
            raise RuntimeError("handler blew up")

    assert get_audit_request_context().ip_address is None, "a failed request left its address bound"


def test_reset_restores_a_nested_outer_value_rather_than_clearing_it():
    outer = set_audit_request_context(build_audit_request_context(ip_address="10.0.0.3"))
    try:
        inner = set_audit_request_context(build_audit_request_context(ip_address="10.0.0.4"))
        assert get_audit_request_context().ip_address == "10.0.0.4"
        reset_audit_request_context(inner)

        assert get_audit_request_context().ip_address == "10.0.0.3"
    finally:
        reset_audit_request_context(outer)

    assert get_audit_request_context().ip_address is None


@pytest.mark.asyncio
async def test_concurrent_tasks_do_not_see_each_others_addresses():
    """Two requests in flight on one event loop must not cross-contaminate.

    ``asyncio.gather`` copies the context per task, so this is the property the
    ContextVar is being relied on for; asserting it here means the reliance is
    tested rather than assumed.
    """
    observed: dict[str, str | None] = {}

    async def handle(name: str, ip: str, delay: float) -> None:
        with audit_request_context(ip_address=ip, user_agent=name):
            await asyncio.sleep(delay)
            observed[name] = get_audit_request_context().ip_address

    await asyncio.gather(
        handle("a", "10.1.1.1", 0.02),
        handle("b", "10.2.2.2", 0.01),
        handle("c", "10.3.3.3", 0.0),
    )

    assert observed == {"a": "10.1.1.1", "b": "10.2.2.2", "c": "10.3.3.3"}


@pytest.mark.asyncio
async def test_a_task_spawned_without_a_request_sees_nothing():
    """A background task started off-request reads absent, not the last request's value."""
    result: dict[str, str | None] = {}

    async def background() -> None:
        result["ip"] = get_audit_request_context().ip_address

    with audit_request_context(ip_address="10.9.9.9", user_agent="req"):
        pass

    await asyncio.create_task(background())

    assert result["ip"] is None


def test_oversized_values_are_clipped_to_the_column_widths():
    """Truncation is here so an oversized header cannot fail the audit flush."""
    context = build_audit_request_context(
        ip_address="9" * 200,
        user_agent="U" * 4000,
    )

    assert len(context.ip_address) == IP_ADDRESS_MAX_LENGTH
    assert len(context.user_agent) == USER_AGENT_MAX_LENGTH


def test_blank_headers_normalise_to_absent_rather_than_empty_string():
    """Null means "not captured"; "" would claim a capture that found nothing."""
    context = build_audit_request_context(ip_address="   ", user_agent="")

    assert context.ip_address is None
    assert context.user_agent is None


def test_the_carrier_imports_nothing_outside_the_standard_library():
    """D09: the domain must be able to read this without importing infrastructure.

    If this module ever grows a FastAPI or src.infrastructure import, the coupling
    that kept ip_address out of PR #1381 is back, and audit_service inherits it.
    """
    import inspect

    from src.domain.context import audit_request_context as module

    source = inspect.getsource(module)
    assert "import fastapi" not in source
    assert "from fastapi" not in source
    assert "from src.infrastructure" not in source
    assert "import src.infrastructure" not in source
    assert "from starlette" not in source
