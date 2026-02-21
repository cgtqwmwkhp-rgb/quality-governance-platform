"""Request context for correlation ID propagation."""

import contextvars
from typing import Optional

request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)


def get_request_id() -> Optional[str]:
    return request_id_var.get()


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)
