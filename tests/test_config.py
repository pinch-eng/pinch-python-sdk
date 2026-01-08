import os
from pathlib import Path

import pytest

from pinch.config import resolve_api_key, write_dotenv_api_key
from pinch.errors import PinchConfigError


def test_missing_api_key_non_interactive_raises(monkeypatch, tmp_path: Path):
    # Avoid reading any real .env in the repo/CWD; run in an isolated directory.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PINCH_API_KEY", raising=False)
    with pytest.raises(PinchConfigError):
        resolve_api_key(None, prompt_if_missing=True, interactive=False)


def test_write_dotenv_writes_only_key(tmp_path: Path):
    p = write_dotenv_api_key("abc123", directory=tmp_path)
    assert p.exists()
    assert p.read_text(encoding="utf-8") == "PINCH_API_KEY=abc123\n"


