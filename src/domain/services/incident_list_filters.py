"""Query parameters the incidents list actually applies in SQL.

Status and severity stay client-side over one page. Captions and range copy
may only treat a total as filtered when the parameter is in this set.
"""

from __future__ import annotations

from src.domain.models.incident import IncidentType

SERVER_FILTERABLE_PARAMS = frozenset(
    {
        "page",
        "page_size",
        "reporter_email",
        "owner",
        "asset_id",
        "ids",
        "search",
        "type",
    }
)

CLIENT_ONLY_LIST_PARAMS = frozenset({"status", "severity", "q", "register"})

INCIDENT_TYPE_VALUES = frozenset(member.value for member in IncidentType)
