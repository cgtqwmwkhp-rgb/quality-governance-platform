"""Query parameters the compliance-schedule list actually applies server-side.

``clause`` and ``framework`` stay client-side over the loaded page.
``register`` is caption identity only. Captions may only treat a total as
filtered when the parameter is in the server set.
"""

from __future__ import annotations

SERVER_FILTERABLE_PARAMS = frozenset(
    {
        "page",
        "page_size",
        "is_active",
        "location_id",
        "status",
        "statutory",
    }
)

CLIENT_ONLY_LIST_PARAMS = frozenset({"clause", "framework", "register", "view"})
