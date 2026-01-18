from __future__ import annotations

import os
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional

from .errors import PinchConfigError


def _is_interactive() -> bool:
    try:
        return bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        return False


def load_api_key_from_env() -> Optional[str]:
    key = os.getenv("PINCH_API_KEY")
    if key:
        return key.strip() or None
    return None


def load_api_key_from_dotenv(*, directory: Optional[Path] = None) -> Optional[str]:
    """
    Load PINCH_API_KEY from a local .env file in the current working directory.
    This avoids re-prompting on every CLI run after the user has saved a key.
    """
    directory = directory or Path.cwd()
    path = directory / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("PINCH_API_KEY="):
            continue
        value = line.split("=", 1)[1].strip()
        # Support quoted values.
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1].strip()
        return value or None

    return None


def write_dotenv_api_key(api_key: str, *, directory: Optional[Path] = None) -> Path:
    directory = directory or Path.cwd()
    path = directory / ".env"
    # Only write exactly the required key.
    path.write_text(f"PINCH_API_KEY={api_key}\n", encoding="utf-8")
    return path


def resolve_api_key(
    api_key: Optional[str] = None,
    *,
    prompt_if_missing: bool = True,
    offer_write_dotenv: bool = True,
    directory: Optional[Path] = None,
    interactive: Optional[bool] = None,
) -> str:
    if api_key and api_key.strip():
        return api_key.strip()

    env_key = load_api_key_from_env()
    if env_key:
        return env_key

    dotenv_key = load_api_key_from_dotenv(directory=directory)
    if dotenv_key:
        return dotenv_key

    if not prompt_if_missing:
        raise PinchConfigError("Missing PINCH_API_KEY.")

    if interactive is None:
        interactive = _is_interactive()

    if not interactive:
        raise PinchConfigError("Missing PINCH_API_KEY. Set it as an environment variable to continue.")

    entered = getpass("Enter your Pinch API key (input hidden): ").strip()
    if not entered:
        raise PinchConfigError("Missing PINCH_API_KEY.")

    if offer_write_dotenv:
        try:
            answer = input("Save to .env in the current directory? [y/N]: ").strip().lower()
        except EOFError:
            answer = "n"
        if answer in ("y", "yes"):
            write_dotenv_api_key(entered, directory=directory)

    return entered


