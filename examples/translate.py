from __future__ import annotations

import asyncio
from pathlib import Path

from pinch import translate_file


async def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    input_wav = examples_dir / "input.wav"
    output_wav = examples_dir / "output.wav"
    transcript_txt = examples_dir / "transcript.txt"

    await translate_file(
        input_wav_path=input_wav,
        output_wav_path=output_wav,
        transcript_path=transcript_txt,
        source_language="en-US",
        target_language="es-ES",
        audio_output_enabled=True,
    )

    print(f"Saved {output_wav}")
    print(f"Saved {transcript_txt}")


if __name__ == "__main__":
    asyncio.run(main())

