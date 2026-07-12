"""Azure Blob storage upstream readiness helpers (Path-to-10 S10 honesty).

Blob storage is optional until operators set AZURE_STORAGE_CONNECTION_STRING.
Readiness reports configuration without secrets; missing credentials stay
``not_configured`` and do not fail the probe.

Circuit metadata for Preferred ``blob_storage`` is informational only — /readyz
never dials Azure Blob or invents connection strings.
"""

from __future__ import annotations

import os
from typing import Any

_BLOB_CIRCUIT_NAME = "blob_storage"


def _present(raw: str | None) -> bool:
    return bool((raw or "").strip())


def _blob_circuit_metadata() -> dict[str, Any]:
    """Return Preferred blob circuit health without inventing breaker state."""
    try:
        from src.infrastructure.resilience.circuit_breaker import get_all_circuits

        registered = {cb.name: cb.get_health() for cb in get_all_circuits()}
    except Exception:
        registered = {}

    if _BLOB_CIRCUIT_NAME in registered:
        return {_BLOB_CIRCUIT_NAME: registered[_BLOB_CIRCUIT_NAME]}
    return {
        _BLOB_CIRCUIT_NAME: {
            "name": _BLOB_CIRCUIT_NAME,
            "state": "unregistered",
            "note": (
                "Circuit registers on first Azure Blob upload/download/delete "
                "via the Preferred catalog facade in this process."
            ),
        }
    }


def get_upstream_storage_readiness() -> dict[str, Any]:
    """Return Azure Blob configuration status without secrets.

    Status values:
    - ``configured``: connection string present (container defaults to attachments)
    - ``partial``: connection string present but container name explicitly empty
    - ``not_configured``: connection string missing
    """
    connection_string = (os.getenv("AZURE_STORAGE_CONNECTION_STRING") or "").strip()
    # Empty env means unset → default container; whitespace-only is mis-set.
    raw_container = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    if raw_container is None:
        container_name = "attachments"
        container_explicitly_empty = False
    else:
        container_name = raw_container.strip()
        container_explicitly_empty = not container_name

    connection_present = _present(connection_string)
    container_present = bool(container_name)

    if connection_present and container_present:
        status = "configured"
    elif connection_present and container_explicitly_empty:
        status = "partial"
    else:
        status = "not_configured"

    library = "unavailable"
    try:
        import azure.storage.blob  # noqa: F401

        library = "azure-storage-blob"
    except ImportError:
        library = "missing"

    payload: dict[str, Any] = {
        "status": status,
        "connection_string_present": connection_present,
        "container_name_present": container_present,
        "container_name": container_name if container_present else None,
        "role": "blob",
        "library": library,
        "circuits": _blob_circuit_metadata(),
        "ping": {
            "status": "skipped",
            "connectivity": "unprobed",
            "note": (
                "Azure Blob ping is not executed on /readyz. "
                "Configuration and Preferred circuit metadata are reported instead; "
                "live blob I/O happens only on evidence/attachment paths."
            ),
        },
    }

    if status == "not_configured":
        payload["note"] = (
            "Azure Blob upstream is not configured. Set AZURE_STORAGE_CONNECTION_STRING "
            "(and optionally AZURE_STORAGE_CONTAINER_NAME; default attachments) via "
            "Key Vault / App Settings when evidence and attachment uploads require cloud storage. "
            "Unset connection string falls back to local filesystem outside production."
        )
    elif status == "partial":
        payload["note"] = (
            "Azure Blob connection string is present but AZURE_STORAGE_CONTAINER_NAME is empty. "
            "Set a container name (or omit the env var to use the attachments default)."
        )
    elif library == "missing":
        payload["note"] = (
            "Azure Blob credentials are present but azure-storage-blob is not installed. "
            "Uploads will fail until the dependency is available in the runtime image."
        )
    return payload
