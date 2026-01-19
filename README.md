# Pinch Python SDK

Real-time speech translation.

## Requirements

- Python **3.10+**
- A Pinch API key ([get one here](https://startpinch.com))

## Quick Start (uv recommended)

```bash
git clone https://github.com/pinch/pinch-python.git
cd pinch-python
export PINCH_API_KEY="your_key_here"
uv run python examples/translate.py
```

## Install from PyPI

```bash
pip install pinch-sdk
```

Or with uv:

```bash
uv add pinch-sdk
```

## Usage

```python
import asyncio
from pinch import translate_file

async def main():
    await translate_file(
        input_wav_path="input.wav",
        output_wav_path="output.wav",
        transcript_path="transcript.txt",
        # source_language="en-US",  # default
        # target_language="es-ES",  # default
    )

asyncio.run(main())
```

## API Key

Set `PINCH_API_KEY` as an environment variable:

```bash
export PINCH_API_KEY="your_key_here"
```

Or create a `.env` file in your project directory:

```
PINCH_API_KEY=your_key_here
```

## Audio Requirements

- Input must be **16-bit PCM WAV**
- Supported sample rates: **16000 Hz** and **48000 Hz**
- Other sample rates require: `pip install "pinch-sdk[audio]"`

## License

MIT
