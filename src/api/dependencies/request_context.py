"""Dependencies for accessing request context data."""

from fastapi import Request


def get_request_id(request: Request) -> str:
    """
    Get the request_id from request.state.

    This dependency provides reliable access to the request_id set by
    RequestStateMiddleware, which works correctly with both synchronous
    TestClient and asynchronous AsyncClient.

    Args:
        request: The FastAPI Request object

    Returns:
        The request_id string (UUID hex format)
    """
    return getattr(request.state, "request_id", "unknown")
