from .client import PinchClient
from .errors import (
    PinchAuthError,
    PinchConfigError,
    PinchError,
    PinchNetworkError,
    PinchPermissionError,
    PinchProtocolError,
    PinchRateLimitError,
    PinchServerError,
    PinchValidationError,
)
from .events import AudioEvent, ErrorEvent, SessionEnded, SessionStarted, TranscriptEvent
from .session import SessionInfo, SessionParams

try:
    from importlib.metadata import version as _pkg_version

    __version__ = _pkg_version("pinch")
except Exception:  # pragma: no cover
    __version__ = "0.1.0"

__all__ = [
    "__version__",
    "PinchClient",
    "SessionParams",
    "SessionInfo",
    "TranscriptEvent",
    "AudioEvent",
    "ErrorEvent",
    "SessionStarted",
    "SessionEnded",
    "PinchError",
    "PinchConfigError",
    "PinchValidationError",
    "PinchAuthError",
    "PinchPermissionError",
    "PinchRateLimitError",
    "PinchServerError",
    "PinchNetworkError",
    "PinchProtocolError",
]


