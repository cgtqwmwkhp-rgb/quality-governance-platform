"""OCR provider ops meta endpoints (Path-to-10 W4 — configuration honesty only).

Reports whether Mistral, Gemini, and Azure DI environment variables are present.
Never returns secrets or dials live OCR providers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from src.infrastructure.upstream.ai_status import get_ocr_providers_readiness

router = APIRouter(tags=["Meta"])


@router.get("/ocr-providers", response_model=dict[str, Any])
async def get_ocr_providers_meta() -> dict[str, Any]:
    """Return OCR provider configuration flags and capability notes (no secrets)."""
    payload = get_ocr_providers_readiness()
    payload["as_of"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["endpoint"] = "/api/v1/health/meta/ocr-providers"
    payload["canonical_endpoint"] = "/api/v1/meta/ocr-providers"
    if not payload.get("note"):
        payload["note"] = "Configuration-only meta; live OCR calls occur on import/analysis paths only."
    return payload
