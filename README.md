## Pinch Python Library

[![PyPI version](https://img.shields.io/pypi/v/pinch-sdk.svg)](https://pypi.org/project/pinch-sdk/)
[![Documentation](https://img.shields.io/badge/docs-startpinch.com-blue.svg)](https://www.startpinch.com/docs)

The Pinch Python library provides convenient access to the Pinch API from applications written in the Python language. It includes a pre-defined set of classes for API resources.

## Installation

Using pip:

```bash
pip install pinch-sdk
```

Using uv:

```bash
uv add pinch-sdk
```

## Requirements

We currently support **Python 3.10+**.

## Usage

### 1. File-based translation

This approach is ideal when:

- you already have an audio file
- you want simple, one-shot translation

Example script from this repo (`examples/translate.py`):

```python
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
        #source_language="en-US",
        #target_language="es-ES",
        #audio_output_enabled=True,
    )

    print("Saved output.wav and transcript.txt")


if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Real-time translation

Streaming sessions are designed for low-latency, real-time use cases.

In this approach:

- audio is streamed in real-time
- transcripts + translated audio is returned in real-time

This example intentionally leaves playback or storage to the user’s preference.

Create a streaming session:

```python
from pinch import PinchClient
from pinch.session import SessionParams

client = PinchClient()

session = client.create_session(
    SessionParams(
        source_language="en-US",
        target_language="es-ES",
    )
)
```

This session represents a live translation context.

Connect a streaming transport:

```python
stream = await client.connect_stream(
    session,
    audio_output_enabled=True,
)
```

Once connected:

- the stream accepts incoming audio
- transcripts and translated audio are returned

Stream audio into Pinch:

Audio is sent as raw PCM16 frames (for example, 20 ms chunks).

```python
await stream.send_pcm16(
    pcm_bytes,
    sample_rate=16000,
    channels=1,
)
```

You can send audio from:

- a microphone
- a WAV file
- another real-time source

Pinch processes audio incrementally as it arrives.

Receive streaming outputs:

Pinch returns results as asynchronous events.

```python
async for event in stream.events():
    if event.type == "transcript":
        # Partial or final transcript text
        print(event.text)

    elif event.type == "audio":
        # Translated speech as raw PCM16 bytes
        pcm_bytes = event.pcm16_bytes
        sample_rate = event.sample_rate

# Forward, buffer, save, or play this audio as needed
```

Audio is returned as data, not played automatically. Applications decide how to handle playback or storage.

Close the stream:

```python
await stream.aclose()
```

Closing the stream signals that no more audio will be sent.

Input audio requirements:

- **16-bit PCM**
- Supported sample rates: **16000 Hz** (recommended) and **48000 Hz**

## Support

New features and bug fixes are released on the latest major version of the SDK. For any issues, contact `support@startpinch.com`.

## Contributing

We welcome contributions!

### Setup

1. Clone this repository:

```bash
git clone https://github.com/startpinch/pinch-python-sdk.git
cd pinch-python-sdk
```

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install the package in editable mode:

```bash
python3 -m pip install -e .
```

### Run tests

```bash
python3 -m pytest
```

### Submitting changes

- Found a bug? Open an [issue](https://github.com/pinch-eng/pinch-python-sdk/issues).
- Have a feature idea? Start a [discussion](https://github.com/pinch-eng/pinch-python-sdk/discussions).
- Want to contribute code? Open a [pull request](https://github.com/pinch-eng/pinch-python-sdk/pulls).

We aim to review all contributions promptly and provide constructive feedback to help get your changes merged.

## Getting Help

- [Join our Discord](https://discord.gg/s8KFeXpP)
- [Read our Docs](https://www.startpinch.com/docs)
- [Reach out on LinkedIn](https://www.linkedin.com/company/startpinch)
- [Reach us on X](https://x.com/StartPinch)
