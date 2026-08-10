"""Read-only notification inventory for the admin surface.

Why this is a separate router
-----------------------------
It reads, and it reads only. Keeping it out of ``src/api/routes/notifications.py``
and away from ``NotificationService`` means the honest-inventory surface cannot
acquire a dispatch side effect by accident, and that concurrent work on the
delivery path and on preference enforcement does not collide with it here.

Why it is gated on ``admin:manage``
-----------------------------------
The payload names every module and callable that produces a notification, which is
an internal map of the deployment, plus which channels are unconfigured — useful to
an operator and useful to an attacker deciding what will not be noticed. A named
permission is also what the route census requires: a superuser gate would push
``Posture.SUPERUSER`` past the ceiling recorded in
``src/domain/authz/route_declarations.py``, and that ceiling exists precisely to
stop endpoints being closed to everyone but the account that bypasses every check.
``admin:manage`` is already enforced elsewhere and already in the catalogue, so
this adds no vocabulary.

Why nothing is seeded
---------------------
``GET /api/v1/feature-flags/{key}`` inserts the Compliance Schedule notify rows if
they are missing, which is right for a page whose next action is a toggle. An
inventory read must not write, so flags are read as they are and a missing row is
reported as unpersisted with its default in force, rather than being created to
make the report tidier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.notification_inventory import NotificationInventoryResponse
from src.domain.models.user import User
from src.domain.notifications.inventory import build_inventory, referenced_flag_keys

router = APIRouter()


def _readiness_payloads() -> dict[str, dict[str, Any]]:
    """Consult each channel status helper.

    A helper that raises is reported as absent rather than allowed to fail the
    request: an inventory that 500s because one optional channel's environment is
    malformed tells an operator less than one that says the channel is not
    configured.
    """
    payloads: dict[str, dict[str, Any]] = {}

    try:
        from src.infrastructure.email.email_status import get_email_readiness

        payloads["smtp"] = get_email_readiness()
    except Exception:  # pragma: no cover - defensive; helpers read env only
        pass

    try:
        from src.infrastructure.push.vapid_status import get_vapid_readiness

        vapid = dict(get_vapid_readiness())
        # The public key is safe to publish and the subscribe flow already serves
        # it, but it is bulk that this report has no use for.
        vapid.pop("public_key", None)
        payloads["vapid"] = vapid
    except Exception:  # pragma: no cover - defensive; helpers read env only
        pass

    try:
        from src.infrastructure.sms.sms_status import get_sms_readiness

        payloads["twilio"] = get_sms_readiness()
    except Exception:  # pragma: no cover - defensive; helpers read env only
        pass

    return payloads


async def _flag_states(db: Any) -> dict[str, Optional[bool]]:
    """Read the persisted state of every flag a producer depends on.

    ``None`` for a key means no row exists. That is not the same as disabled —
    these flags default to on when absent — so the distinction is preserved all
    the way to the response instead of being flattened here.
    """
    keys = referenced_flag_keys()
    states: dict[str, Optional[bool]] = {key: None for key in keys}
    if not keys:
        return states

    try:
        from src.domain.services.feature_flag_service import FeatureFlagService

        for flag in await FeatureFlagService(db).list_flags():
            key = str(flag.key)
            if key in states:
                states[key] = bool(flag.enabled)
    except Exception:
        # An unreadable flag table leaves every key unpersisted, which the
        # response renders as "default in force" rather than as "off".
        return {key: None for key in keys}

    return states


@router.get(
    "",
    response_model=NotificationInventoryResponse,
    summary="Notification channel and producer inventory",
    description=(
        "What this deployment can actually notify: the delivery channels that exist and whether "
        "each is configured to send, the events that produce notifications, and the producers that "
        "are implemented but that no production path reaches. Read-only."
    ),
)
async def get_notification_inventory(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> NotificationInventoryResponse:
    inventory = build_inventory(
        readiness_payloads=_readiness_payloads(),
        flag_states=await _flag_states(db),
    )
    return NotificationInventoryResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        **inventory,
    )
