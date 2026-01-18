from __future__ import annotations

from typing import Any, Optional


class PinchError(Exception):
    """Base error for the Pinch SDK."""


class PinchConfigError(PinchError):
    """Configuration error (missing/invalid PINCH_API_KEY, etc.)."""


class PinchValidationError(PinchError):
    """Local validation error before a network call."""


class PinchAuthError(PinchError):
    """Authentication failed."""


class PinchPermissionError(PinchError):
    """Permission/credits error."""


class PinchRateLimitError(PinchError):
    """Rate limit error."""


class PinchServerError(PinchError):
    """Pinch service returned a server error."""


class PinchNetworkError(PinchError):
    """Network error (timeouts, disconnects)."""


class PinchProtocolError(PinchError):
    """Unexpected response/event shapes."""


def map_http_error(status_code: int, payload: Optional[Any]) -> PinchError:
    """
    Map HTTP status codes to SDK exception types with safe, user-friendly messages.
    Never mention internal transport/session architecture terms.
    """
    raw: Optional[dict[str, Any]] = payload if isinstance(payload, dict) else None

    if status_code == 401:
        return PinchAuthError("Authentication failed. Check your PINCH_API_KEY in the Pinch Portal.")
    if status_code in (402, 403):
        return PinchPermissionError("No credits available. Please add credits in the Pinch Portal.")
    if status_code == 400:
        # Prefer service-provided validation message if present (it typically references request fields).
        if isinstance(payload, dict):
            msg = payload.get("error") or payload.get("message")
            if isinstance(msg, str) and msg.strip():
                return PinchValidationError(msg.strip())
        return PinchValidationError("Invalid request. Please check your inputs and try again.")
    if status_code == 429:
        return PinchRateLimitError("Too many requests. Please try again shortly.")
    if 500 <= status_code <= 599:
        return PinchServerError("Service is temporarily unavailable. Please try again.")

    # Default: keep it generic and safe.
    return PinchProtocolError("Unexpected response from the service. Please try again.")


