## Pinch Python SDK

### Requirements

- Python **3.9+**
- A Pinch API key in `PINCH_API_KEY`

### Authentication (`PINCH_API_KEY`)

The SDK reads the API key from:

1) `PINCH_API_KEY` environment variable (recommended)
2) A local `.env` file in your current working directory (optional)

Example `.env` file (optional):

```env
PINCH_API_KEY=your_key_here
```

### Install (pip)

```bash
python3 -m pip install pinch
```

### Install (uv)

In a uv-managed project:

```bash
uv add pinch
```

### Library usage

Create a small script (for example `translate.py`) in your own project:

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

if __name__ == "__main__":
    asyncio.run(main())
```

Run (pip environment):

```bash
export PINCH_API_KEY="..."
python3 translate.py
```

Run (uv environment):

```bash
export PINCH_API_KEY="..."
uv run python translate.py
```

Outputs:

- `output.wav`
- `transcript.txt`

### Input audio notes

- Input must be **16-bit PCM WAV**
- Supported sample rates out of the box: **16000 Hz** and **48000 Hz**
- Other sample rates require resampling deps: `python3 -m pip install "pinch[audio]"`

### Repo example (for this git checkout)

This repository includes an example script and a default input WAV.

Run with pip:

```bash
python3 -m pip install -e .
export PINCH_API_KEY="..."
python3 examples/translate.py
```

Run with uv:

```bash
uv sync
export PINCH_API_KEY="..."
uv run python examples/translate.py
```

Outputs (generated):

- `examples/output.wav`
- `examples/transcript.txt`

Notes:

- The example reads `examples/input.wav` by default.
- The example does not print transcripts to stdout; it only writes `examples/transcript.txt`.
