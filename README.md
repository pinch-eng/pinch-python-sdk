## Pinch Python SDK

### Install

```bash
python3 -m pip install pinch
```

Python requirement: **Python 3.9+**

### Library usage (production)

After installing, create a small script (for example `translate.py`) that imports the SDK:

```python
import asyncio
from pinch import translate_file

async def main() -> None:
    await translate_file(
        input_wav_path="input.wav",
        output_wav_path="output.wav",
        transcript_path="transcript.txt",
        # defaults:
        # source_language="en-US"
        # target_language="es-ES"
        # audio_output_enabled=True
        # voiceType is always "clone"
    )

asyncio.run(main())
```

Run it:

```bash
export PINCH_API_KEY="..."
python3 translate.py
```

This writes:

- `output.wav`
- `transcript.txt`

Input audio notes:

- Input WAV must be **16-bit PCM**.
- Sample rates supported out of the box: **16000 Hz** and **48000 Hz**.
- Other sample rates require installing optional resampling deps: `pip install "pinch[audio]"`.

### Repo example script (for this git checkout)

```bash
python3 -m pip install -e .
export PINCH_API_KEY="..."
python3 examples/translate.py
```

This writes:

- `examples/output.wav`
- `examples/transcript.txt`

Notes:

- The example reads `examples/input.wav` by default.
- `voiceType` is always `"clone"` in the example script.

### SDK usage (imports)

Use `PinchClient`, `SessionParams`, and `PinchStream` from the `pinch` package, or call the helper in `pinch.file_translate`.
