"""Response contract for the notification inventory.

Read-only throughout: there is no request body and no update schema, because the
endpoint reports what exists rather than changing it.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChannelReadiness(BaseModel):
    """One delivery channel, and whether this deployment can send on it."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Channel identifier. Real channels match a NotificationChannel enum value.")
    label: str
    implemented: bool = Field(description="False for a channel this product does not have at all.")
    transport: Optional[str] = Field(default=None, description="What carries the message.")
    readiness: str = Field(description="ready, degraded, not_configured, disabled, or not_implemented.")
    can_send: bool = Field(description="Whether a send on this channel can currently leave the process.")
    readiness_source: Optional[str] = Field(
        default=None, description="Which server-side status helper decided the readiness."
    )
    status_detail: Optional[str] = Field(default=None, description="The status helper's own note, when it gave one.")
    diagnostics: dict[str, Any] = Field(
        default_factory=dict,
        description="The status helper's payload verbatim. Presence flags only; never a secret value.",
    )
    note: str = Field(description="What an operator should understand about the channel regardless of state.")


class ProducerFeatureFlag(BaseModel):
    """A feature flag a producer depends on, and its persisted state."""

    key: str
    enabled: bool = Field(description="Effective value. An absent row defaults to enabled.")
    persisted: bool = Field(description="False when no feature_flags row exists yet and the default is in force.")


class NotificationProducer(BaseModel):
    """An event that creates notifications, or one that is written but unreachable."""

    id: str
    event: str
    module: str = Field(description="Repository-relative path of the module that creates the notification.")
    symbol: str = Field(description="Callable in that module which does it.")
    channels: list[str] = Field(
        description="Channel ids reached. 'preferences' means resolved per recipient from NotificationPreference."
    )
    trigger: str = Field(description="request or schedule.")
    schedule: Optional[str] = Field(default=None, description="Cadence for scheduled producers.")
    beat_task: Optional[str] = Field(default=None, description="Celery beat entry that drives a scheduled producer.")
    feature_flags: list[ProducerFeatureFlag] = Field(default_factory=list)
    status: str = Field(description="active, or no_production_caller when nothing outside the module calls it.")
    note: str


class NotificationInventorySummary(BaseModel):
    """Counts, so a caller does not have to derive them to render a headline."""

    channels_implemented: int
    channels_can_send: int
    producers_total: int
    producers_active: int
    producers_without_caller: int = Field(
        description="Producers that exist in the source and that no production path reaches."
    )


class NotificationInventoryResponse(BaseModel):
    """Honest inventory of notification channels and producers for this deployment."""

    generated_at: str = Field(description="When this snapshot was taken, ISO 8601 UTC.")
    channels: list[ChannelReadiness]
    producers: list[NotificationProducer]
    summary: NotificationInventorySummary
