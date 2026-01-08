from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import PinchProtocolError, PinchValidationError


_ALLOWED_VOICE_TYPES = {"clone", "male", "female"}


@dataclass(frozen=True)
class SessionParams:
    source_language: str = "en-US"
    target_language: str = "es-ES"
    voice_type: str = "clone"  # allowed: clone, male, female
    audio_output_enabled: bool = True

    def validate(self) -> None:
        if self.voice_type not in _ALLOWED_VOICE_TYPES:
            raise PinchValidationError(
                "Invalid voice_type. Allowed values: clone, male, female."
            )
        if not self.source_language or not self.target_language:
            raise PinchValidationError("source_language and target_language are required.")


@dataclass(frozen=True)
class SessionInfo:
    url: str
    token: str
    room_name: str
    raw: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_response(payload: Any) -> "SessionInfo":
        if not isinstance(payload, dict):
            raise PinchProtocolError("Unexpected response from the service. Please try again.")

        url = payload.get("url")
        token = payload.get("token")
        room_name = payload.get("room_name")

        if not isinstance(url, str) or not url:
            raise PinchProtocolError("Unexpected response from the service. Please try again.")
        if not isinstance(token, str) or not token:
            raise PinchProtocolError("Unexpected response from the service. Please try again.")
        if not isinstance(room_name, str) or not room_name:
            raise PinchProtocolError("Unexpected response from the service. Please try again.")

        return SessionInfo(url=url, token=token, room_name=room_name, raw=payload)


