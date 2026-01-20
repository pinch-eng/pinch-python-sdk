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
from .file_translate import FileTranslateResult, translate_file
from .session import SessionInfo, SessionParams

from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("pinch-sdk")
except Exception:
    __version__ = "0.1.1"


__all__ = [
    "__version__",
    "PinchClient",
    "SessionParams",
    "SessionInfo",
    "translate_file",
    "FileTranslateResult",
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


