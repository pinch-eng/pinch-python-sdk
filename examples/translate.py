from __future__ import annotations

import asyncio
from pathlib import Path

from pinch import PinchClient


async def main() -> None:
    examples_dir = Path(__file__).resolve().parent

    client = PinchClient()

    await client.translate_file(
        input_wav_path=examples_dir / "input.wav",
        output_wav_path=examples_dir / "output.wav",
        transcript_path=examples_dir / "transcript.txt",
        source_language="en-US",
        target_language="es-ES",
        audio_output_enabled=True,
    )

    print("Saved output.wav and transcript.txt")


if __name__ == "__main__":
    asyncio.run(main())

