"""What this deployment can actually notify, and whether it is configured to.

Why this file exists
--------------------
``/admin/notifications`` used to answer "does this platform send email?" with four
channel cards whose switches wrote to ``useState`` and nothing else. FR-HONESTY-
SWEEP-01 deleted them, which removed the lie but left the question unanswered: an
administrator still had no way to find out which channels exist, which are
configured, or what events actually produce a notification. This module is the
answer, and it is deliberately a *declaration* rather than a control panel — every
field is read from source or from server state, and nothing here can be toggled.

Why a declaration rather than a runtime scan
--------------------------------------------
A registry computed by walking the import graph could not disagree with the code,
so a test comparing them would pass no matter what — the vacuity that
:mod:`src.domain.authz.catalogue` documents for the permission vocabulary. Writing
the producers down as literals means adding one shows up as a reviewable diff, and
``tests/unit/test_notification_inventory.py`` fails until the declaration and the
source agree. That test does three things a scan could not:

1. resolves every :attr:`ProducerDeclaration.module` and
   :attr:`ProducerDeclaration.symbol` against the tree, so an entry cannot name
   code that does not exist;
2. greps for the ways a notification row is actually created and requires every
   module it finds to be declared here, so a *new* producer cannot ship
   undeclared;
3. checks :attr:`ProducerDeclaration.referenced` against whether anything outside
   the declaring module calls it, so "implemented but never triggered" cannot be
   presented as a working feature.

That third property is the point. Four helpers on ``NotificationService`` —
SOS alerts, RIDDOR alerts, competency expiry and @mention fan-out — are fully
written and reachable only from unit tests. An inventory that listed them
alongside the live producers would be the same category of dishonesty as the
toggles that were deleted, so they are declared with ``referenced=False`` and
reported as having no production caller. The number of live producers is
deliberately not written out here: a count in prose is a claim no test checks,
and this one had already drifted.

What this file does not do
--------------------------
It does not dispatch, gate, or alter delivery. :mod:`src.domain.services.
notification_service` owns the delivery path and nothing here is imported by it;
the readiness classification below only interprets payloads that the caller
obtains from the ``src.infrastructure`` status helpers, because ``src/domain`` may
not import ``src/infrastructure`` outside the allowlist in
``scripts/check_import_boundaries.py``. Keeping the interpretation pure is also
what lets the whole vocabulary be tested without an app, a database or an
environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

# --------------------------------------------------------------------------- #
# Readiness vocabulary
# --------------------------------------------------------------------------- #

#: The channel is configured and a send can leave the process.
READY = "ready"
#: The channel will send, but something about the configuration is wrong enough
#: to be worth an operator's attention.
DEGRADED = "degraded"
#: The channel cannot send. Sends are skipped or fail.
NOT_CONFIGURED = "not_configured"
#: Ops has explicitly switched the channel off.
DISABLED = "disabled"
#: No such channel exists in this product.
NOT_IMPLEMENTED = "not_implemented"

READINESS_VALUES: frozenset[str] = frozenset({READY, DEGRADED, NOT_CONFIGURED, DISABLED, NOT_IMPLEMENTED})

#: Where a channel's readiness comes from. ``"none"`` means the channel needs no
#: external configuration, so there is nothing for an operator to get wrong.
READINESS_SOURCES: frozenset[str] = frozenset({"none", "smtp", "vapid", "twilio"})

#: How a producer is set off.
TRIGGER_REQUEST = "request"
TRIGGER_SCHEDULE = "schedule"


# --------------------------------------------------------------------------- #
# Declarations
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ChannelDeclaration:
    """A delivery channel that ``NotificationService`` really branches on."""

    #: Must equal a ``NotificationChannel`` enum value.
    id: str
    label: str
    #: What carries the message, named concretely enough to be checked.
    transport: str
    #: Which ``src.infrastructure`` status helper decides this channel's readiness.
    readiness_source: str
    #: What an operator should understand about the channel regardless of state.
    note: str


@dataclass(frozen=True)
class AbsentChannelDeclaration:
    """A channel people expect to find here and that does not exist.

    Recorded rather than omitted: the deleted "Webhook Integration" card taught
    administrators that this platform has a webhook notification channel, and a
    surface that simply stops mentioning webhooks does not correct that. Naming
    the absence, and where the nearby real feature lives, does.
    """

    id: str
    label: str
    reason: str


@dataclass(frozen=True)
class ProducerDeclaration:
    """An event in this product that creates notifications."""

    id: str
    #: The event in the language of the person who would receive it.
    event: str
    #: Repository-relative path of the module that creates the notification.
    module: str
    #: A callable defined in ``module`` that does it.
    symbol: str
    #: Channel ids this producer can reach. ``("preferences",)`` means it calls
    #: ``NotificationService`` and the channels are resolved per recipient from
    #: ``NotificationPreference``, so the answer is not fixed here.
    channels: tuple[str, ...]
    trigger: str
    #: Human reading of the cadence. ``None`` for request-triggered producers.
    schedule: Optional[str]
    #: Dotted name of the Celery beat entry that drives this producer, which is
    #: what makes :attr:`schedule` checkable: the test requires this to be a task
    #: really present in ``celery_app.conf.beat_schedule``, so a producer cannot
    #: claim a cadence that no scheduler would honour.
    beat_task: Optional[str]
    #: Feature-flag keys that must be on for this producer to send.
    feature_flags: tuple[str, ...]
    #: Whether anything outside ``module`` calls ``symbol``. ``False`` means the
    #: code exists and no production path reaches it.
    referenced: bool
    note: str


#: Delivery channels, exactly as ``NotificationService.create_notification``
#: branches on them. The test asserts these ids are the ``NotificationChannel``
#: enum, in both directions, so a channel cannot be added to the product without
#: appearing here and this list cannot claim one the dispatcher does not know.
CHANNELS: tuple[ChannelDeclaration, ...] = (
    ChannelDeclaration(
        id="in_app",
        label="In-app",
        transport="notifications table row, pushed over the /realtime websocket",
        readiness_source="none",
        note=(
            "Needs no configuration, and the row is written regardless of the channel decision, so "
            "an in-app notification is never lost, whether or not the "
            "recipient is connected. The websocket only decides whether they see it without "
            "reloading, and since FR-NOTIF-ADMIN-03 that push is subject to the recipient's category "
            "preferences. Quiet hours do not hold it back: it is passive."
        ),
    ),
    ChannelDeclaration(
        id="email",
        label="Email",
        transport="Celery send_email task, then aiosmtplib via EmailService",
        readiness_source="smtp",
        note=(
            "Enqueued to the Celery notifications path, so a send needs a running worker as well as "
            "SMTP credentials. Without credentials EmailService reports itself disabled and the task "
            "returns skipped rather than pretending to have sent. Subject to the recipient's category "
            "preferences; deliberately not held back by quiet hours, since no digest queue exists to "
            "defer it to."
        ),
    ),
    ChannelDeclaration(
        id="sms",
        label="SMS",
        transport="Twilio REST API via SMSService",
        readiness_source="twilio",
        note=(
            "Only ever selected for critical and high priority notifications, and only when the "
            "recipient has a phone number on their NotificationPreference row. Since "
            "FR-NOTIF-ADMIN-03 it is also held back during the recipient's quiet hours unless the "
            "notification is critical. Every condition is per recipient, so a configured channel is "
            "still not a guaranteed send."
        ),
    ),
    ChannelDeclaration(
        id="push",
        label="Web push",
        transport="Celery send_push_notification task, then pywebpush with VAPID keys",
        readiness_source="vapid",
        note=(
            "Needs a VAPID key pair and at least one browser subscription for the recipient, and "
            "since FR-NOTIF-ADMIN-03 is held back during quiet hours unless the notification is "
            "critical. With no subscription the task has nowhere to send and skips, which is "
            "indistinguishable from a healthy send in the channel's own readiness."
        ),
    ),
)

#: Channels this product does not have. Declared so the admin surface can say so
#: outright instead of leaving an administrator to infer it from an absence.
ABSENT_CHANNELS: tuple[AbsentChannelDeclaration, ...] = (
    AbsentChannelDeclaration(
        id="webhook",
        label="Webhook",
        reason=(
            "NotificationChannel has no webhook member and NotificationService has no webhook "
            "branch, so no notification has ever been deliverable this way. Outbound HTTP to third "
            "parties exists as a separate subsystem with its own subscriptions and delivery log, at "
            "/admin/partner-webhooks; it is driven by partner events rather than by notifications."
        ),
    ),
    AbsentChannelDeclaration(
        id="digest",
        label="Email digest",
        reason=(
            "No periodic digest job exists. The NotificationPreference table still carries "
            "email_digest_enabled and email_digest_frequency columns, and nothing reads them: "
            "FR-HONESTY-SWEEP-01 removed the weekly-summary controls that implied otherwise. Every "
            "email below is sent per event."
        ),
    ),
)

#: Every event that creates a notification, and the four helpers that could but
#: never do. Verified against the tree by
#: ``tests/unit/test_notification_inventory.py``, which also refuses a producer
#: module it finds in the source and does not find here.
PRODUCERS: tuple[ProducerDeclaration, ...] = (
    ProducerDeclaration(
        id="action_owner_assigned",
        event="An action is assigned to an owner, or its owner changes",
        module="src/domain/services/action_assignment_service.py",
        symbol="notify_action_assignment",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Reached from action create and action update in src/api/routes/actions.py.",
    ),
    ProducerDeclaration(
        id="audit_run_assigned",
        event="An audit run is assigned to a person, or its assignee changes",
        module="src/domain/services/audit_assignment_notify.py",
        symbol="notify_audit_scheduled",
        channels=("in_app", "email"),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note=(
            "Reached from audit run create and update in src/api/routes/audits.py. "
            "The action_url is /portal/audits (Employee Portal), not the staff execute shell. "
            "Notify failure does not roll back the assignee write."
        ),
    ),
    ProducerDeclaration(
        id="audit_finding_capa_closure",
        event="A CAPA closure changes the state of the audit finding it answers",
        module="src/domain/services/audit_service.py",
        symbol="notify_capa_closure_bridge",
        channels=("in_app",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note=(
            "Status notifications are in-app only by construction: create_status passes "
            "channels=[IN_APP] rather than letting the recipient's channel toggles widen it. The two "
            "outcomes gate differently. Pending verification sends AUDIT_FINDING, which "
            "FR-NOTIF-ADMIN-03 maps to audit_notifications, so that toggle can hold the websocket "
            "push back. Closure sends ACTION_COMPLETED at MEDIUM priority, and no category owns that "
            "type, so no toggle can suppress it. The row is written either way."
        ),
    ),
    ProducerDeclaration(
        id="assessment_run_complete",
        event="A competency assessment run is completed",
        module="src/api/routes/assessments.py",
        symbol="complete_assessment",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Notifies the assessed engineer and their supervisor as two separate notifications.",
    ),
    ProducerDeclaration(
        id="induction_run_complete",
        event="An induction run is completed",
        module="src/api/routes/inductions.py",
        symbol="complete_induction",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Notifies the inducted engineer and their supervisor as two separate notifications.",
    ),
    ProducerDeclaration(
        id="complaint_owner_assigned",
        event="A complaint is allocated to a case owner",
        module="src/api/routes/complaints.py",
        symbol="_notify_case_owner_assignment",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Fires on reassignment as well as first allocation.",
    ),
    ProducerDeclaration(
        id="incident_owner_assigned",
        event="An incident is allocated to a case owner",
        module="src/api/routes/incidents.py",
        symbol="_notify_case_owner_assignment",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=("incident_owner_assignment_notify",),
        referenced=True,
        note=(
            "Fires on reassignment as well as first allocation. Gated by "
            "incident_owner_assignment_notify (default-off: missing row means no send)."
        ),
    ),
    ProducerDeclaration(
        id="portal_intake_triaged",
        event="An anonymous employee-portal report is triaged to an owner",
        module="src/domain/services/portal_triage_service.py",
        symbol="assign_and_notify_portal_intake",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Reached from the portal submit path in src/api/routes/employee_portal.py.",
    ),
    ProducerDeclaration(
        id="compliance_schedule_owner_assigned",
        event="A Compliance Schedule obligation is allocated to an owner",
        module="src/domain/services/compliance_schedule_assignment_notify.py",
        symbol="notify_compliance_schedule_owner_assignment",
        channels=("in_app", "email"),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=("compliance_schedule_assignment_notify", "compliance_schedule_email_enabled"),
        referenced=True,
        note=(
            "The two flags are the toggles kept on this page. Email additionally needs SMTP and the "
            "recipient's own email preference; the Compliance Schedule kill switch closes both."
        ),
    ),
    ProducerDeclaration(
        id="compliance_schedule_due_reminder",
        event="A Compliance Schedule obligation falls due or goes overdue",
        module="src/infrastructure/tasks/compliance_schedule_notification_tasks.py",
        symbol="sweep_compliance_schedule_due",
        channels=("in_app", "email"),
        trigger=TRIGGER_SCHEDULE,
        schedule="daily 08:15 UTC",
        beat_task="src.infrastructure.tasks.compliance_schedule_notification_tasks.sweep_compliance_schedule_due",
        feature_flags=("compliance_schedule_due_reminder_notify", "compliance_schedule_email_enabled"),
        referenced=True,
        note=(
            "Deduplicates per obligation occurrence, so completing a cycle rolls next_due_date and "
            "stops that occurrence's reminders rather than repeating them daily."
        ),
    ),
    ProducerDeclaration(
        id="ces_import_pending_lookups",
        event="A CES asset import creates provisional asset types or locations needing approval",
        module="src/domain/services/ces_asset_import_service.py",
        symbol="_notify_pending_lookups",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Notifies tenant superusers, who are the only people who can approve the provisional rows.",
    ),
    ProducerDeclaration(
        id="training_matrix_proposal",
        event="A training frequency matrix change is proposed and awaits approval",
        module="src/api/routes/training_matrix.py",
        symbol="propose_requirements_matrix",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Notifies the approvers who can accept or reject the proposed matrix.",
    ),
    ProducerDeclaration(
        id="training_matrix_upload_reminder",
        event="No training matrix has been uploaded recently",
        module="src/infrastructure/tasks/training_matrix_upload_reminder_tasks.py",
        symbol="remind_training_matrix_upload",
        channels=("in_app",),
        trigger=TRIGGER_SCHEDULE,
        schedule="weekly, Friday 08:00 UTC",
        beat_task="src.infrastructure.tasks.training_matrix_upload_reminder_tasks.remind_training_matrix_upload",
        feature_flags=(),
        referenced=True,
        note="Deduplicated per ISO week, so a missed upload produces one reminder rather than one per run.",
    ),
    ProducerDeclaration(
        id="safety_asset_expiry",
        event="A safety asset certificate approaches or passes its expiry",
        module="src/infrastructure/tasks/safety_asset_expiry_tasks.py",
        symbol="check_safety_asset_expiry",
        channels=("in_app",),
        trigger=TRIGGER_SCHEDULE,
        schedule="daily 07:30 UTC",
        beat_task="src.infrastructure.tasks.safety_asset_expiry_tasks.check_safety_asset_expiry",
        feature_flags=(),
        referenced=True,
        note="Deduplicated per asset and expiry band, so an asset does not re-notify within the same band.",
    ),
    ProducerDeclaration(
        id="document_campaign_assignment",
        event="A document read-and-understood campaign assigns a document to someone",
        module="src/domain/services/document_campaign_service.py",
        symbol="launch_campaign",
        channels=("in_app", "email"),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note=(
            "Writes the notification row and sends campaign mail through EmailService directly, not "
            "through NotificationService — so the FR-NOTIF-ADMIN-03 category-preference and "
            "quiet-hours gates do not apply to this mail."
        ),
    ),
    ProducerDeclaration(
        id="document_campaign_reminder",
        event="A document campaign assignment is due or overdue",
        module="src/domain/services/document_campaign_service.py",
        symbol="process_due_reminders",
        channels=("in_app", "email"),
        trigger=TRIGGER_SCHEDULE,
        schedule="hourly at :15",
        beat_task="src.infrastructure.tasks.document_campaign_tasks.process_campaign_reminders",
        feature_flags=(),
        referenced=True,
        note="Runs from the process_campaign_reminders Celery task and covers both due reminders and overdue escalation.",
    ),
    ProducerDeclaration(
        id="vehicle_defect_p1",
        event="A P1 vehicle defect is flagged",
        module="src/api/routes/vehicle_checklists.py",
        symbol="_create_p1_notification",
        channels=("in_app",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note=(
            "Notifies tenant superusers. Failures are swallowed and logged so that a notification "
            "problem cannot stop the defect itself being recorded."
        ),
    ),
    ProducerDeclaration(
        id="pams_defect_batch",
        event="A PAMS checklist sync auto-detects vehicle defects",
        module="src/infrastructure/tasks/pams_sync_tasks.py",
        symbol="_send_p1_notifications",
        channels=("in_app",),
        trigger=TRIGGER_SCHEDULE,
        schedule="every 15 minutes",
        beat_task="src.infrastructure.tasks.pams_sync_tasks.sync_pams_checklists",
        feature_flags=(),
        referenced=True,
        note="Suppressed while an unread batch notification already exists, so a persistent defect does not notify every quarter hour.",
    ),
    ProducerDeclaration(
        id="standards_assessment_links",
        event="Operational standards links are proposed against a case",
        module="src/domain/services/standards_assessment_notifications.py",
        symbol="notify_proposed_standards_links",
        channels=("in_app",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=True,
        note="Reached from the governed knowledge assessment path.",
    ),
    # ----------------------------------------------------------------------- #
    # Written, and reached by nothing but unit tests.
    # ----------------------------------------------------------------------- #
    ProducerDeclaration(
        id="sos_alert",
        event="A lone worker raises an SOS",
        module="src/domain/services/notification_service.py",
        symbol="send_sos_alert",
        channels=("in_app", "email", "sms", "push"),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=False,
        note=(
            "No production caller. The method is complete and tested, and no route, service or task "
            "invokes it, so raising an SOS in this product notifies nobody."
        ),
    ),
    ProducerDeclaration(
        id="riddor_alert",
        event="An incident is assessed as RIDDOR reportable",
        module="src/domain/services/notification_service.py",
        symbol="send_riddor_alert",
        channels=("in_app", "email", "sms", "push"),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=False,
        note=(
            "No production caller. RIDDOR reportability is recorded on the incident without "
            "notifying anyone that the statutory clock has started."
        ),
    ),
    ProducerDeclaration(
        id="competency_expiry",
        event="An engineer's competency approaches expiry",
        module="src/domain/services/notification_service.py",
        symbol="notify_competency_expiry",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=False,
        note=(
            "No production caller. The check_competency_expiry Celery task runs daily at 07:00 UTC "
            "and does not call this, so expiring competencies produce no notification."
        ),
    ),
    ProducerDeclaration(
        id="mention_fanout",
        event="Someone is @mentioned in a comment or note",
        module="src/domain/services/notification_service.py",
        symbol="process_mentions",
        channels=("preferences",),
        trigger=TRIGGER_REQUEST,
        schedule=None,
        beat_task=None,
        feature_flags=(),
        referenced=False,
        note=(
            "No production caller. Mention parsing and the mention search endpoint both work, and "
            "nothing calls the fan-out, so being @mentioned notifies nobody."
        ),
    ),
)


# --------------------------------------------------------------------------- #
# Readiness interpretation
# --------------------------------------------------------------------------- #


def classify_readiness(source: str, payload: Optional[Mapping[str, Any]]) -> str:
    """Reduce a status helper's payload to one of :data:`READINESS_VALUES`.

    The distinction being drawn is only "can this channel send": ``READY`` and
    ``DEGRADED`` both can, ``NOT_CONFIGURED`` and ``DISABLED`` cannot. The
    upstream payload travels alongside this in the response, so nothing this
    collapses is hidden — a caller that needs to know *which* key is missing
    reads the diagnostics rather than this value.
    """
    if source == "none":
        return READY
    if payload is None:
        # A helper that could not be consulted is not evidence of readiness.
        return NOT_CONFIGURED

    status = str(payload.get("status") or "").strip()
    library_ok = payload.get("library") != "missing"

    if source == "smtp":
        if status == "configured":
            return READY
        # EmailService enables itself on credentials alone, so this really does
        # send; EMAIL_ENABLED being unset means nobody has said it should.
        if status == "credentials_present":
            return DEGRADED
        return NOT_CONFIGURED

    if source == "vapid":
        if status != "configured":
            return NOT_CONFIGURED
        return READY if library_ok else NOT_CONFIGURED

    if source == "twilio":
        if status == "disabled":
            return DISABLED
        if status != "configured":
            return NOT_CONFIGURED
        if not library_ok:
            return NOT_CONFIGURED
        # Credentials without a from-number are accepted by Twilio's client and
        # rejected by its API, so this sends until it does not.
        return READY if payload.get("twilio_from_number_present") else DEGRADED

    return NOT_CONFIGURED


def can_send(readiness: str) -> bool:
    """Whether a channel in this state can actually deliver."""
    return readiness in (READY, DEGRADED)


# --------------------------------------------------------------------------- #
# Report assembly
# --------------------------------------------------------------------------- #


def build_channels(readiness_payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Describe each real channel, folding in the readiness payload for its source.

    ``readiness_payloads`` is keyed by :attr:`ChannelDeclaration.readiness_source`.
    A source with no entry is reported as not configured rather than omitted: a
    channel missing from this list would read as a channel that does not exist.
    """
    channels: list[dict[str, Any]] = []
    for declaration in CHANNELS:
        payload = readiness_payloads.get(declaration.readiness_source)
        readiness = classify_readiness(declaration.readiness_source, payload)
        channels.append(
            {
                "id": declaration.id,
                "label": declaration.label,
                "implemented": True,
                "transport": declaration.transport,
                "readiness": readiness,
                "can_send": can_send(readiness),
                "readiness_source": declaration.readiness_source,
                "status_detail": (payload or {}).get("note") or None,
                "diagnostics": dict(payload) if payload else {},
                "note": declaration.note,
            }
        )
    for absent in ABSENT_CHANNELS:
        channels.append(
            {
                "id": absent.id,
                "label": absent.label,
                "implemented": False,
                "transport": None,
                "readiness": NOT_IMPLEMENTED,
                "can_send": False,
                "readiness_source": None,
                "status_detail": None,
                "diagnostics": {},
                "note": absent.reason,
            }
        )
    return channels


def build_producers(flag_states: Mapping[str, Optional[bool]]) -> list[dict[str, Any]]:
    """Describe each producer, folding in the state of the flags that gate it.

    ``flag_states`` maps a feature-flag key to its persisted value, or to ``None``
    when no row exists. ``None`` is reported as each flag family's default rather
    than forced off: Compliance Schedule notify flags default **on**; Incident
    notify flags default **off**. Showing the wrong default would invert the
    behaviour an operator is trying to understand.
    """
    from src.domain.services.incident_notify_flags import DEFAULT_OFF_FLAG_KEYS

    producers: list[dict[str, Any]] = []
    for declaration in PRODUCERS:
        flags = []
        for key in declaration.feature_flags:
            persisted_value = flag_states.get(key)
            if persisted_value is None:
                default_on = key not in DEFAULT_OFF_FLAG_KEYS
                enabled = default_on
                persisted = False
            else:
                enabled = bool(persisted_value)
                persisted = True
            flags.append(
                {
                    "key": key,
                    "enabled": enabled,
                    "persisted": persisted,
                }
            )
        producers.append(
            {
                "id": declaration.id,
                "event": declaration.event,
                "module": declaration.module,
                "symbol": declaration.symbol,
                "channels": list(declaration.channels),
                "trigger": declaration.trigger,
                "schedule": declaration.schedule,
                "beat_task": declaration.beat_task,
                "feature_flags": flags,
                "status": "active" if declaration.referenced else "no_production_caller",
                "note": declaration.note,
            }
        )
    return producers


def build_inventory(
    *,
    readiness_payloads: Mapping[str, Mapping[str, Any]],
    flag_states: Mapping[str, Optional[bool]],
) -> dict[str, Any]:
    """Assemble the whole inventory. Pure: every input is supplied by the caller."""
    channels = build_channels(readiness_payloads)
    producers = build_producers(flag_states)

    return {
        "channels": channels,
        "producers": producers,
        "summary": {
            "channels_implemented": sum(1 for c in channels if c["implemented"]),
            "channels_can_send": sum(1 for c in channels if c["can_send"]),
            "producers_total": len(producers),
            "producers_active": sum(1 for p in producers if p["status"] == "active"),
            "producers_without_caller": sum(1 for p in producers if p["status"] == "no_production_caller"),
        },
    }


def referenced_flag_keys() -> tuple[str, ...]:
    """Feature-flag keys named by any producer, de-duplicated and sorted.

    Derived rather than listed so a caller knows which rows to read without
    restating the set and letting it drift from :data:`PRODUCERS`.
    """
    keys: set[str] = set()
    for declaration in PRODUCERS:
        keys.update(declaration.feature_flags)
    return tuple(sorted(keys))


__all__ = [
    "ABSENT_CHANNELS",
    "CHANNELS",
    "DEGRADED",
    "DISABLED",
    "NOT_CONFIGURED",
    "NOT_IMPLEMENTED",
    "PRODUCERS",
    "READINESS_SOURCES",
    "READINESS_VALUES",
    "READY",
    "TRIGGER_REQUEST",
    "TRIGGER_SCHEDULE",
    "AbsentChannelDeclaration",
    "ChannelDeclaration",
    "ProducerDeclaration",
    "build_channels",
    "build_inventory",
    "build_producers",
    "can_send",
    "classify_readiness",
    "referenced_flag_keys",
]
