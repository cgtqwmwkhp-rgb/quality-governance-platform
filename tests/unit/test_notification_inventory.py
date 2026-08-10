"""Hold the notification inventory to the source it claims to describe.

The inventory's whole value is that an administrator can believe it. A registry of
literals can drift from the code the moment somebody adds a producer, and a drifted
inventory is worse than none: it is the vapourware
``/admin/notifications`` used to render, moved server-side and given the authority
of an API.

So the checks here are deliberately adversarial about the three ways it could lie:

* **Claiming code that is not there.** Every declared module must exist and every
  declared symbol must be defined in it.
* **Missing a producer.** The source is scanned for the ways a notification row is
  actually created, and any module found that is not declared fails the suite. New
  producers therefore cannot ship silently.
* **Presenting dead code as a feature.** ``referenced`` is checked against whether
  anything outside the declaring module calls the symbol, in both directions, so a
  producer nothing triggers cannot be listed as active and a live one cannot be
  written off.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from src.domain.models.notification import NotificationChannel
from src.domain.notifications.inventory import (
    ABSENT_CHANNELS,
    CHANNELS,
    DEGRADED,
    DISABLED,
    NOT_CONFIGURED,
    PRODUCERS,
    READINESS_SOURCES,
    READINESS_VALUES,
    READY,
    TRIGGER_REQUEST,
    TRIGGER_SCHEDULE,
    build_inventory,
    can_send,
    classify_readiness,
    referenced_flag_keys,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

#: The dispatcher itself, plus the ORM model. Both mention notification creation
#: because they *are* the mechanism, so neither is a producer of any event.
NON_PRODUCER_MODULES: dict[str, str] = {
    "src/domain/models/notification.py": "declares the Notification model; creates nothing",
    "src/domain/services/notification_service.py": (
        "is the dispatcher. Its own uncalled helpers are declared as producers with referenced=False; "
        "the create_notification machinery around them is not an event."
    ),
}

#: Markers that mean "this module creates a notification". ``Notification(`` is
#: matched with a preceding non-word character so ``PushNotification(`` and
#: ``NotificationService(`` do not count.
_DIRECT_MARKERS = (
    re.compile(r"(?<![A-Za-z0-9_.])Notification\("),
    re.compile(r"\.create_notification\("),
    re.compile(r"\.create_bulk_notifications\("),
)

#: Helper methods on ``NotificationService``. A bare ``create_status(`` is far too
#: common a name to treat as proof on its own, so these only count in a module that
#: also names ``NotificationService``.
_HELPER_NAMES = (
    "create_assignment",
    "create_status",
    "notify_assessment_complete",
    "notify_induction_complete",
    "notify_competency_expiry",
    "process_mentions",
    "send_sos_alert",
    "send_riddor_alert",
)
_HELPER_MARKERS = tuple(re.compile(rf"\.{name}\(") for name in _HELPER_NAMES)


def _python_sources() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _defined_symbols(path: Path) -> set[str]:
    """Every function or method name defined anywhere in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _scan_producer_modules() -> set[str]:
    """Modules whose source creates a notification, found by reading the tree."""
    found: set[str] = set()
    for path in _python_sources():
        text = path.read_text(encoding="utf-8")
        # Definition lines are not call sites: SMSService defines its own
        # send_sos_alert, which sends an SMS and creates no notification.
        body = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("def ", "async def ")))

        if any(marker.search(body) for marker in _DIRECT_MARKERS):
            found.add(_rel(path))
            continue
        if "NotificationService" in body and any(marker.search(body) for marker in _HELPER_MARKERS):
            found.add(_rel(path))
    return found


def _entry_point_kind(path: Path, symbol: str) -> str | None:
    """Whether ``symbol`` is invoked by a framework rather than by Python code.

    A FastAPI handler and a Celery task are both reachable without anything in the
    tree calling them, so "no call site" is not evidence that a producer is dead.
    Decorators are read rather than assumed: a handler that has lost its route
    decorator really is unreachable, and this reports it as such.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != symbol:
            continue
        for decorator in node.decorator_list:
            rendered = ast.unparse(decorator)
            if re.search(r"\brouter\.(get|post|put|patch|delete)\b", rendered):
                return "route"
            if re.search(r"\b(celery_app\.task|shared_task)\b", rendered):
                return "task"
    return None


def _call_sites(symbol: str) -> set[str]:
    """Modules that call ``symbol``, excluding the lines that define it."""
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(symbol)}\(")
    callers: set[str] = set()
    for path in _python_sources():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("def ", "async def ")):
                continue
            if pattern.search(line):
                callers.add(_rel(path))
                break
    return callers


# --------------------------------------------------------------------------- #
# Guards against this file passing without checking anything
# --------------------------------------------------------------------------- #


def test_the_source_tree_is_actually_being_read() -> None:
    """Without this, every scan below is vacuously satisfied by an empty result."""
    sources = _python_sources()
    assert len(sources) > 200, f"only {len(sources)} python files found under {SRC}; the scan is not reading the tree"
    assert _scan_producer_modules(), "the producer scan found nothing, so it cannot be catching anything either"


def test_the_registry_is_not_empty() -> None:
    assert PRODUCERS, "no producers declared"
    assert CHANNELS, "no channels declared"


# --------------------------------------------------------------------------- #
# Channels must be the channels the dispatcher has
# --------------------------------------------------------------------------- #


def test_declared_channels_are_exactly_the_dispatcher_channels() -> None:
    """Both directions: no invented channel, and no channel left out."""
    declared = {channel.id for channel in CHANNELS}
    actual = {member.value for member in NotificationChannel}
    assert declared == actual, (
        f"declared channels {sorted(declared)} do not match NotificationChannel {sorted(actual)}. "
        "A channel the dispatcher cannot deliver on must not be advertised, and one it can must not "
        "be hidden."
    )


def test_absent_channels_really_are_absent() -> None:
    """A channel declared as not implemented must not exist in the enum."""
    absent = {channel.id for channel in ABSENT_CHANNELS}
    actual = {member.value for member in NotificationChannel}
    overlap = absent & actual
    assert not overlap, f"{sorted(overlap)} are declared absent but NotificationChannel has them"


def test_absent_channels_explain_themselves() -> None:
    for channel in ABSENT_CHANNELS:
        assert len(channel.reason.strip()) > 60, (
            f"{channel.id} is declared absent without a real explanation. Saying a channel does not "
            "exist is only useful with the reason and the nearest real alternative."
        )


def test_channel_readiness_sources_are_known() -> None:
    for channel in CHANNELS:
        assert (
            channel.readiness_source in READINESS_SOURCES
        ), f"{channel.id} names unknown source {channel.readiness_source}"


def test_in_app_is_the_only_channel_needing_no_configuration() -> None:
    """A channel claiming it needs nothing configured is claiming it always works."""
    unconditional = {channel.id for channel in CHANNELS if channel.readiness_source == "none"}
    assert unconditional == {"in_app"}, (
        f"{sorted(unconditional)} claim to need no configuration. Only in-app does: its row is "
        "persisted regardless of transport. Every other channel needs credentials someone can omit."
    )


# --------------------------------------------------------------------------- #
# Producers must name real code
# --------------------------------------------------------------------------- #


def test_producer_ids_are_unique() -> None:
    ids = [producer.id for producer in PRODUCERS]
    duplicates = sorted({identifier for identifier in ids if ids.count(identifier) > 1})
    assert not duplicates, f"duplicate producer ids: {duplicates}"


def test_every_declared_producer_module_exists() -> None:
    missing = sorted(p.module for p in PRODUCERS if not (REPO_ROOT / p.module).is_file())
    assert not missing, f"declared producer modules that do not exist: {missing}"


def test_every_declared_producer_symbol_is_defined_in_its_module() -> None:
    """A declaration pointing at a callable that is not there describes nothing."""
    wrong: list[str] = []
    for producer in PRODUCERS:
        path = REPO_ROOT / producer.module
        if not path.is_file():
            continue  # reported by the test above
        if producer.symbol not in _defined_symbols(path):
            wrong.append(f"{producer.id}: {producer.symbol} is not defined in {producer.module}")
    assert not wrong, "producer declarations name symbols their module does not define:\n" + "\n".join(wrong)


def test_producer_channels_are_known() -> None:
    known = {channel.id for channel in CHANNELS} | {"preferences"}
    unknown: list[str] = []
    for producer in PRODUCERS:
        assert producer.channels, f"{producer.id} declares no channels"
        for channel in producer.channels:
            if channel not in known:
                unknown.append(f"{producer.id}: {channel}")
    assert not unknown, f"producers naming channels that do not exist: {unknown}"


def test_producer_feature_flags_are_the_compliance_schedule_notify_flags() -> None:
    """The only producers gated by a flag today are the Compliance Schedule pair.

    This pins the claim the admin page makes: the toggles it still renders are the
    flags these producers actually read. A new flag key here without a matching
    row in ``compliance_schedule_notify_flags`` — or elsewhere — would be a
    toggle with nothing behind it, which is what FR-HONESTY-SWEEP-01 removed.
    """
    from src.domain.services.compliance_schedule_notify_flags import NOTIFY_FLAG_KEYS

    declared = set(referenced_flag_keys())
    assert declared <= set(NOTIFY_FLAG_KEYS), (
        f"{sorted(declared - set(NOTIFY_FLAG_KEYS))} are declared as gating a producer but are not "
        "Compliance Schedule notify flags. Either the flag is real and its module should say so, or "
        "the producer is not actually gated."
    )


# --------------------------------------------------------------------------- #
# The census: a producer cannot ship undeclared
# --------------------------------------------------------------------------- #


def test_every_producer_module_in_the_source_is_declared() -> None:
    """The fail-closed gate. A new notification producer must be declared here.

    If this fails for code you have just added, add a ``ProducerDeclaration`` for
    it — including ``referenced=False`` if nothing calls it yet. Adding the module
    to ``NON_PRODUCER_MODULES`` is only correct when it genuinely creates no
    notification, and that mapping requires a reason.
    """
    found = _scan_producer_modules()
    declared = {producer.module for producer in PRODUCERS}
    undeclared = sorted(found - declared - set(NON_PRODUCER_MODULES))
    assert not undeclared, (
        "these modules create notifications and are not in src/domain/notifications/inventory.py:\n"
        + "\n".join(f"  {module}" for module in undeclared)
        + "\nThe inventory is what /admin/notifications reports, so an undeclared producer is a "
        "notification the platform sends and does not admit to."
    )


def test_no_declaration_describes_a_module_the_scan_cannot_see() -> None:
    """A declared module the scan does not recognise means the scan has gone blind.

    The census above can only be trusted if its detection still matches how this
    codebase writes producers. A declared producer that the scan misses is
    evidence that some other, undeclared producer written the same way is also
    being missed.
    """
    found = _scan_producer_modules()
    invisible = sorted({p.module for p in PRODUCERS} - found)
    assert not invisible, (
        "the producer scan does not detect notification creation in these declared modules:\n"
        + "\n".join(f"  {module}" for module in invisible)
        + "\nEither the module no longer produces notifications, or the scan's markers need "
        "extending — in which case it has been under-reporting."
    )


def test_non_producer_exclusions_are_justified_and_used() -> None:
    found = _scan_producer_modules()
    for module, reason in NON_PRODUCER_MODULES.items():
        assert (REPO_ROOT / module).is_file(), f"excluded module {module} does not exist"
        assert len(reason.strip()) > 20, f"{module} is excluded without a real reason"
        assert module in found, (
            f"{module} is excluded from the producer census but the scan does not flag it anyway. "
            "A pointless exemption hides the next real one."
        )


# --------------------------------------------------------------------------- #
# Dead code must not be presented as a feature
# --------------------------------------------------------------------------- #


def test_producers_declared_unreferenced_have_no_production_caller() -> None:
    """``referenced=False`` must mean nothing in src/ calls it.

    If this fails, the producer has been wired up since it was declared, and the
    honest change is ``referenced=True`` — the inventory reporting a working
    feature as broken is its own kind of wrong.
    """
    wrong: list[str] = []
    for producer in PRODUCERS:
        if producer.referenced:
            continue
        callers = _call_sites(producer.symbol) - {producer.module}
        if callers:
            wrong.append(f"{producer.id}: {producer.symbol} is called from {sorted(callers)}")
        kind = _entry_point_kind(REPO_ROOT / producer.module, producer.symbol)
        if kind:
            wrong.append(f"{producer.id}: {producer.symbol} is reachable as a {kind} entry point")
    assert not wrong, "producers declared as having no production caller are in fact reachable:\n" + "\n".join(wrong)


def test_producers_declared_active_are_reachable() -> None:
    """``referenced=True`` must mean something can actually reach it.

    Reachable means called from somewhere, or entered by a framework: six of these
    producers are FastAPI handlers or Celery tasks that no Python code calls by
    name. A producer listed as active that satisfies neither is the exact failure
    this inventory exists to expose, so it is not allowed to be introduced by the
    inventory itself.
    """
    unreachable: list[str] = []
    for producer in PRODUCERS:
        if not producer.referenced:
            continue
        path = REPO_ROOT / producer.module
        if _call_sites(producer.symbol) or _entry_point_kind(path, producer.symbol):
            continue
        unreachable.append(f"{producer.id}: nothing calls {producer.symbol} and it is not an entry point")
    assert not unreachable, "producers declared active that nothing can reach:\n" + "\n".join(unreachable)


def test_entry_point_detection_actually_finds_entry_points() -> None:
    """Guard the exemption above: if this blinds, every dead handler passes.

    ``_entry_point_kind`` is the only reason six active producers are allowed to
    have no call site. If it silently stopped recognising decorators it would hand
    out that exemption to nothing and quietly hand it to everything instead.
    """
    kinds = {
        producer.id: _entry_point_kind(REPO_ROOT / producer.module, producer.symbol)
        for producer in PRODUCERS
        if producer.referenced
    }

    assert kinds["assessment_run_complete"] == "route"
    assert kinds["induction_run_complete"] == "route"
    assert kinds["training_matrix_proposal"] == "route"
    assert kinds["safety_asset_expiry"] == "task"
    assert kinds["compliance_schedule_due_reminder"] == "task"
    assert kinds["training_matrix_upload_reminder"] == "task"
    # A plain service function must not be mistaken for an entry point, or the
    # exemption would cover producers that genuinely need a caller.
    assert (
        _entry_point_kind(REPO_ROOT / "src/domain/services/action_assignment_service.py", "notify_action_assignment")
        is None
    )


def test_the_known_dead_producers_are_still_recorded() -> None:
    """Pins the four helpers that exist and notify nobody.

    Recorded as a named expectation rather than a count so that wiring one up is a
    deliberate edit to this list, and so deleting a declaration cannot quietly
    make the gap disappear from the report.
    """
    dead = {producer.symbol for producer in PRODUCERS if not producer.referenced}
    assert dead == {
        "send_sos_alert",
        "send_riddor_alert",
        "notify_competency_expiry",
        "process_mentions",
    }, (
        f"the set of implemented-but-unreachable producers changed to {sorted(dead)}. If one has been "
        "wired up, remove it here and set referenced=True. If a new one appeared, that is a feature "
        "that notifies nobody."
    )


# --------------------------------------------------------------------------- #
# Schedules must be schedules something honours
# --------------------------------------------------------------------------- #


def test_request_triggered_producers_declare_no_schedule() -> None:
    for producer in PRODUCERS:
        if producer.trigger != TRIGGER_REQUEST:
            continue
        assert producer.schedule is None, f"{producer.id} is request-triggered but declares a schedule"
        assert producer.beat_task is None, f"{producer.id} is request-triggered but names a beat task"


def test_scheduled_producers_name_a_real_celery_beat_entry() -> None:
    """A declared cadence must correspond to a task beat actually runs."""
    from src.infrastructure.tasks.celery_app import celery_app

    beat_tasks = {entry.get("task") for entry in celery_app.conf.beat_schedule.values()}
    assert beat_tasks, "celery beat_schedule is empty, so this check would pass vacuously"

    problems: list[str] = []
    for producer in PRODUCERS:
        if producer.trigger != TRIGGER_SCHEDULE:
            continue
        if not producer.schedule:
            problems.append(f"{producer.id} is scheduled but declares no cadence")
        if not producer.beat_task:
            problems.append(f"{producer.id} is scheduled but names no beat task")
        elif producer.beat_task not in beat_tasks:
            problems.append(f"{producer.id} names beat task {producer.beat_task}, which beat does not schedule")
    assert not problems, "\n".join(problems)


def test_every_producer_trigger_is_known() -> None:
    for producer in PRODUCERS:
        assert producer.trigger in (TRIGGER_REQUEST, TRIGGER_SCHEDULE), f"{producer.id} has trigger {producer.trigger}"


def test_every_producer_note_says_something() -> None:
    for producer in PRODUCERS:
        assert len(producer.note.strip()) > 20, f"{producer.id} has no meaningful note"


# --------------------------------------------------------------------------- #
# Readiness classification
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "source,payload,expected",
    [
        ("none", None, READY),
        # An unconsulted helper is not evidence of readiness.
        ("smtp", None, NOT_CONFIGURED),
        ("vapid", None, NOT_CONFIGURED),
        ("twilio", None, NOT_CONFIGURED),
        ("smtp", {"status": "configured"}, READY),
        ("smtp", {"status": "credentials_present"}, DEGRADED),
        ("smtp", {"status": "misconfigured"}, NOT_CONFIGURED),
        ("smtp", {"status": "not_configured"}, NOT_CONFIGURED),
        ("vapid", {"status": "configured", "library": "ok"}, READY),
        # Keys without the library cannot send, so this is not merely degraded.
        ("vapid", {"status": "configured", "library": "missing"}, NOT_CONFIGURED),
        ("vapid", {"status": "partial", "library": "ok"}, NOT_CONFIGURED),
        ("vapid", {"status": "not_configured", "library": "ok"}, NOT_CONFIGURED),
        ("twilio", {"status": "disabled"}, DISABLED),
        ("twilio", {"status": "configured", "library": "ok", "twilio_from_number_present": True}, READY),
        ("twilio", {"status": "configured", "library": "ok", "twilio_from_number_present": False}, DEGRADED),
        ("twilio", {"status": "configured", "library": "missing", "twilio_from_number_present": True}, NOT_CONFIGURED),
        ("twilio", {"status": "misconfigured"}, NOT_CONFIGURED),
    ],
)
def test_classify_readiness(source: str, payload: dict | None, expected: str) -> None:
    assert classify_readiness(source, payload) == expected


def test_classify_readiness_never_invents_a_value() -> None:
    for source in READINESS_SOURCES:
        for status in ("configured", "partial", "disabled", "misconfigured", "not_configured", "", "nonsense"):
            assert classify_readiness(source, {"status": status}) in READINESS_VALUES


def test_can_send_is_true_exactly_when_a_send_can_leave() -> None:
    assert can_send(READY)
    assert can_send(DEGRADED)
    assert not can_send(NOT_CONFIGURED)
    assert not can_send(DISABLED)


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #


def test_unconfigured_deployment_reports_nothing_ready_but_in_app() -> None:
    """The default posture must be honest, not optimistic.

    An empty environment is the state a fresh deployment is in, and the report for
    it has to say that email, SMS and push do not send.
    """
    inventory = build_inventory(readiness_payloads={}, flag_states={})
    by_id = {channel["id"]: channel for channel in inventory["channels"]}

    assert by_id["in_app"]["can_send"] is True
    for channel_id in ("email", "sms", "push"):
        assert by_id[channel_id]["can_send"] is False, f"{channel_id} claims it can send with nothing configured"
        assert by_id[channel_id]["readiness"] == NOT_CONFIGURED
    assert inventory["summary"]["channels_can_send"] == 1


def test_absent_channels_are_reported_as_not_implemented() -> None:
    inventory = build_inventory(readiness_payloads={}, flag_states={})
    by_id = {channel["id"]: channel for channel in inventory["channels"]}

    assert "webhook" in by_id, "the report should say outright that there is no webhook channel"
    assert by_id["webhook"]["implemented"] is False
    assert by_id["webhook"]["can_send"] is False
    assert inventory["summary"]["channels_implemented"] == len(CHANNELS)


def test_readiness_payload_is_passed_through_as_diagnostics() -> None:
    """The collapsed readiness must not be the only thing an operator can see."""
    inventory = build_inventory(
        readiness_payloads={"smtp": {"status": "misconfigured", "smtp_user_present": False, "note": "why"}},
        flag_states={},
    )
    email = next(channel for channel in inventory["channels"] if channel["id"] == "email")

    assert email["diagnostics"]["smtp_user_present"] is False
    assert email["status_detail"] == "why"


def test_a_missing_flag_row_reports_its_default_rather_than_off() -> None:
    """These flags default to on when absent; reporting them off would invert them."""
    inventory = build_inventory(readiness_payloads={}, flag_states={key: None for key in referenced_flag_keys()})
    flags = [flag for producer in inventory["producers"] for flag in producer["feature_flags"]]

    assert flags, "no producer flags in the report"
    for flag in flags:
        assert flag["enabled"] is True
        assert flag["persisted"] is False


def test_a_disabled_flag_row_is_reported_disabled() -> None:
    inventory = build_inventory(
        readiness_payloads={},
        flag_states={key: False for key in referenced_flag_keys()},
    )
    flags = [flag for producer in inventory["producers"] for flag in producer["feature_flags"]]

    for flag in flags:
        assert flag["enabled"] is False
        assert flag["persisted"] is True


def test_summary_counts_agree_with_the_lists() -> None:
    inventory = build_inventory(readiness_payloads={}, flag_states={})
    summary = inventory["summary"]

    assert summary["producers_total"] == len(inventory["producers"]) == len(PRODUCERS)
    assert summary["producers_active"] + summary["producers_without_caller"] == summary["producers_total"]
    assert summary["producers_without_caller"] == sum(1 for p in PRODUCERS if not p.referenced)


def test_every_channel_appears_even_when_its_helper_is_silent() -> None:
    """A channel omitted from the report reads as a channel that does not exist.

    The failure mode being excluded is a helper raising or returning nothing and
    its channel quietly vanishing, which would understate the surface rather than
    report it as unconfigured.
    """
    inventory = build_inventory(readiness_payloads={}, flag_states={})
    reported = {channel["id"] for channel in inventory["channels"]}

    assert {channel.id for channel in CHANNELS} <= reported
    assert {channel.id for channel in ABSENT_CHANNELS} <= reported
