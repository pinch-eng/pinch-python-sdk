from pinch.stream import _parse_transcript_payload


def test_parse_transcript_payload_includes_language_detected():
    payload = {
        "type": "original_transcript",
        "text": "Hello world",
        "is_final": True,
        "language_detected": "en-US",
    }
    ev = _parse_transcript_payload(payload)
    assert ev is not None
    assert ev.kind == "original"
    assert ev.text == "Hello world"
    assert ev.is_final is True
    assert ev.language_detected == "en-US"
    assert ev.raw == payload


def test_parse_transcript_payload_invalid_language_detected_defaults_none():
    payload = {
        "type": "translated_transcript",
        "text": "Hola",
        "is_final": True,
        "language_detected": 123,
    }
    ev = _parse_transcript_payload(payload)
    assert ev is not None
    assert ev.kind == "translated"
    assert ev.language_detected is None
