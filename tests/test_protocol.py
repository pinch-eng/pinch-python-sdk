import pytest

from pinch.errors import (
    PinchAuthError,
    PinchPermissionError,
    PinchProtocolError,
    PinchRateLimitError,
    PinchServerError,
    PinchValidationError,
    map_http_error,
)
from pinch.session import SessionInfo


def test_session_response_normalization_missing_fields():
    with pytest.raises(PinchProtocolError):
        SessionInfo.from_response({"url": "x", "token": "y"})  # room_name missing


def test_http_error_mapping():
    assert isinstance(map_http_error(401, {}), PinchAuthError)
    assert isinstance(map_http_error(402, {}), PinchPermissionError)
    assert isinstance(map_http_error(403, {}), PinchPermissionError)
    assert isinstance(map_http_error(400, {}), PinchValidationError)
    assert isinstance(map_http_error(429, {}), PinchRateLimitError)
    assert isinstance(map_http_error(500, {}), PinchServerError)


