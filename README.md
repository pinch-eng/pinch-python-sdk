## Pinch Python SDK

### Install

From this repo:

```bash
pip install -e .
```

Optional extras:

```bash
pip install -e ".[mic]"      # microphone capture + audio playback
pip install -e ".[audio]"    # resampling (for non-16k/48k input WAVs)
```

### Configure

Run in your project directory:

```bash
pinch configure
```

This writes a local `.env` file containing only:

- `PINCH_API_KEY=...`

### File demo

1) Put a WAV file at `examples/input.wav`

2) Run:

```bash
pinch translate --in examples/input.wav --out examples/output.wav --source en-US --target es-ES
```

Notes:
- This will write translated audio to `--out` and also write a transcript file next to it (same name, `.txt`).
- If you omit `--out`, outputs are written to `./results/output.wav` and `./results/output.txt`
- For transcript-only runs (no output WAV), use `--no-audio`. In this mode, `--out` is treated as the transcript path:

```bash
pinch translate --in examples/input.wav --no-audio --out examples/output.txt --source en-US --target es-ES
```

### SDK usage

```python
import asyncio
from pinch import PinchClient, SessionParams

async def main():
    client = PinchClient()  # loads PINCH_API_KEY or prompts if interactive
    session = client.create_session(SessionParams(source_language="en-US", target_language="es-ES"))
    stream = await client.connect_stream(session, audio_output_enabled=True)
    async with stream:
        async for event in stream.events():
            if event.type == "transcript" and event.text:
                prefix = "ORIG" if event.kind == "original" else "TRAN"
                print(f"{prefix}: {event.text}")

asyncio.run(main())
```


