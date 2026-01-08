import pytest

from pinch.errors import PinchValidationError
from pinch.session import SessionParams


def test_voice_type_validation():
    with pytest.raises(PinchValidationError):
        SessionParams(voice_type="invalid").validate()


