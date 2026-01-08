from __future__ import annotations

import contextlib
import time
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .errors import PinchProtocolError


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    sampwidth: int


def read_wav(path: str | Path) -> tuple[WavInfo, bytes]:
    p = Path(path)
    with wave.open(str(p), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            raise PinchProtocolError("Only 16-bit PCM WAV input is supported.")
        frames = wf.readframes(wf.getnframes())
    return WavInfo(sample_rate=sample_rate, channels=channels, sampwidth=sampwidth), frames


def write_wav(path: str | Path, *, pcm16_bytes: bytes, sample_rate: int, channels: int) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(int(channels))
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm16_bytes)


def _require_soxr() -> tuple[object, object]:
    try:
        import numpy as np  # type: ignore
        import soxr  # type: ignore

        return np, soxr
    except Exception as e:
        raise PinchProtocolError(
            "Unsupported input sample rate. Install with: pip install -e \".[audio]\""
        ) from e


def resample_pcm16_mono(pcm16_bytes: bytes, *, from_rate: int, to_rate: int) -> bytes:
    if from_rate == to_rate:
        return pcm16_bytes
    np, soxr = _require_soxr()
    x = np.frombuffer(pcm16_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    y = soxr.resample(x, from_rate, to_rate)
    y_i16 = (np.clip(y, -1.0, 1.0) * 32767.0).astype(np.int16)
    return y_i16.tobytes()


def iter_pcm_frames(
    pcm16_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
    frame_ms: int = 20,
) -> Iterator[bytes]:
    if channels != 1:
        raise PinchProtocolError("Only mono audio is supported.")
    bytes_per_sample = 2
    frame_samples = int(sample_rate * frame_ms / 1000)
    frame_bytes = frame_samples * bytes_per_sample
    for i in range(0, len(pcm16_bytes), frame_bytes):
        chunk = pcm16_bytes[i : i + frame_bytes]
        if len(chunk) < frame_bytes:
            # pad to full frame
            chunk = chunk + b"\x00" * (frame_bytes - len(chunk))
        yield chunk


def wav_to_pcm16_mono_16k(path: str | Path) -> bytes:
    info, data = read_wav(path)
    if info.channels == 2:
        data = stereo_to_mono_pcm16(data)
        info = WavInfo(sample_rate=info.sample_rate, channels=1, sampwidth=2)
    if info.channels != 1:
        raise PinchProtocolError("Only mono or stereo WAV input is supported.")
    if info.sample_rate not in (16000, 48000):
        return resample_pcm16_mono(data, from_rate=info.sample_rate, to_rate=16000)
    if info.sample_rate == 48000:
        return resample_pcm16_mono(data, from_rate=48000, to_rate=16000)
    return data


def stereo_to_mono_pcm16(pcm16_bytes: bytes) -> bytes:
    """
    Convert interleaved stereo PCM16 (little-endian) to mono by averaging L/R.
    """
    samples = array("h")
    samples.frombytes(pcm16_bytes)
    # 'h' uses native endianness; WAV PCM16 is little-endian.
    # If running on big-endian, byteswap to interpret correctly.
    import sys

    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) % 2 != 0:
        samples = samples[: len(samples) - 1]
    mono = array("h")
    for i in range(0, len(samples), 2):
        mono.append(int((samples[i] + samples[i + 1]) / 2))
    if sys.byteorder != "little":
        mono.byteswap()
    return mono.tobytes()


@contextlib.contextmanager
def realtime_sleep(frame_ms: int) -> Iterator[callable]:
    """
    Helper for streaming audio in \"real time-ish\" chunks.
    """
    start = time.perf_counter()
    sent = 0

    def tick() -> None:
        nonlocal sent
        sent += 1
        target = start + (sent * frame_ms / 1000.0)
        now = time.perf_counter()
        if target > now:
            time.sleep(target - now)

    yield tick


