from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional, Union


@dataclass(frozen=True)
class SessionStarted:
    type: Literal["session_started"] = "session_started"


@dataclass(frozen=True)
class SessionEnded:
    type: Literal["session_ended"] = "session_ended"


@dataclass(frozen=True)
class TranscriptEvent:
    type: Literal["transcript"] = "transcript"
    kind: Literal["original", "translated"] = "original"
    text: str = ""
    is_final: Optional[bool] = None
    raw: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class AudioEvent:
    type: Literal["audio"] = "audio"
    pcm16_bytes: bytes = b""
    sample_rate: int = 48000
    channels: int = 1


@dataclass(frozen=True)
class ErrorEvent:
    type: Literal["error"] = "error"
    message: str = ""
    code: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


PinchEvent = Union[SessionStarted, SessionEnded, TranscriptEvent, AudioEvent, ErrorEvent]


