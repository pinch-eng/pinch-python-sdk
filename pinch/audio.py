from __future__ import annotations

import contextlib
import time
import wave
from array import array
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Union

from .errors import PinchProtocolError


@dataclass(frozen=True)
class WavInfo:
    sample_rate: int
    channels: int
    sampwidth: int


def read_wav(path: Union[str, Path]) -> tuple[WavInfo, bytes]:
    p = Path(path)
    with wave.open(str(p), "rb") as wf:
        channels = wf.getnchannels()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        if sampwidth != 2:
            raise PinchProtocolError("Only 16-bit PCM WAV input is supported.")
        frames = wf.readframes(wf.getnframes())
    return WavInfo(sample_rate=sample_rate, channels=channels, sampwidth=sampwidth), frames


def write_wav(path: Union[str, Path], *, pcm16_bytes: bytes, sample_rate: int, channels: int) -> None:
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
            "Unsupported input sample rate. Supported: 16000 Hz or 48000 Hz WAV. "
            "For other sample rates, install resampling deps with: pip install \"pinch-sdk[audio]\""
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


def wav_to_pcm16_mono_pcm16(path: Union[str, Path]) -> tuple[int, bytes]:
    """
    Load a PCM16 WAV file and return (sample_rate, mono_pcm16_bytes).
    """
    info, data = read_wav(path)
    if info.channels == 2:
        data = stereo_to_mono_pcm16(data)
        info = WavInfo(sample_rate=info.sample_rate, channels=1, sampwidth=2)
    if info.channels != 1:
        raise PinchProtocolError("Only mono or stereo WAV input is supported.")
    return int(info.sample_rate), data


def wav_to_pcm16_mono_supported(path: Union[str, Path]) -> tuple[int, bytes]:
    """
    Load a WAV file as mono PCM16 and return (sample_rate, pcm16_bytes).

    Supported without optional deps:
    - 16000 Hz
    - 48000 Hz

    Other sample rates will be resampled to 16000 Hz if the optional audio
    dependencies are installed; otherwise an error is raised.
    """
    sr, pcm = wav_to_pcm16_mono_pcm16(path)
    if sr in (16000, 48000):
        return sr, pcm

    # Best-effort: resample other rates to 16k (requires optional deps).
    return 16000, resample_pcm16_mono(pcm, from_rate=sr, to_rate=16000)


def wav_to_pcm16_mono_16k(path: Union[str, Path]) -> bytes:
    """
    Backwards-compatible helper: return mono PCM16 resampled to 16kHz if needed.
    """
    sr, pcm = wav_to_pcm16_mono_supported(path)
    if sr == 16000:
        return pcm
    if sr == 48000:
        return resample_pcm16_mono(pcm, from_rate=48000, to_rate=16000)
    # wav_to_pcm16_mono_supported only returns 16k or 48k.
    return pcm


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


def trim_pcm16_silence(
    pcm16_bytes: bytes,
    *,
    sample_rate: int,
    channels: int,
    frame_ms: int = 20,
    pad_ms: int = 100,
    max_leading_s: float = 5.0,
    max_trailing_s: float = 10.0,
    threshold: Optional[int] = None,
) -> bytes:
    """
    Trim leading/trailing silence from PCM16 (little-endian) audio.

    - Works without numpy/soxr.
    - Intended for post-processing translated audio to remove long silent head/tail.
    - If the audio is all silence (or too short), returns the original bytes.
    """
    if not pcm16_bytes:
        return pcm16_bytes
    if channels != 1:
        # Keep it conservative: only trim mono output.
        return pcm16_bytes
    if sample_rate <= 0:
        return pcm16_bytes

    samples = array("h")
    samples.frombytes(pcm16_bytes)
    if not samples:
        return pcm16_bytes

    # Interpret WAV PCM16 as little-endian.
    import sys

    if sys.byteorder != "little":
        samples.byteswap()

    frame_samples = max(1, int(sample_rate * frame_ms / 1000.0))
    total = len(samples)
    if total < frame_samples:
        return pcm16_bytes

    # Compute per-frame RMS in int16 units.
    rms: list[int] = []
    max_rms = 0
    for i in range(0, total, frame_samples):
        chunk = samples[i : min(i + frame_samples, total)]
        if not chunk:
            break
        # sum of squares (avoid float); rms ~= sqrt(mean(x^2))
        ss = 0
        for s in chunk:
            ss += int(s) * int(s)
        v = int((ss / max(1, len(chunk))) ** 0.5)
        rms.append(v)
        if v > max_rms:
            max_rms = v

    if max_rms == 0:
        # All zeros.
        return pcm16_bytes

    # Dynamic threshold by default; keep a small absolute floor to avoid trimming on noise.
    thr = int(threshold) if threshold is not None else max(200, int(max_rms * 0.06))

    first_idx: Optional[int] = None
    last_idx: Optional[int] = None
    for idx, v in enumerate(rms):
        if v > thr:
            first_idx = idx
            break
    for idx in range(len(rms) - 1, -1, -1):
        if rms[idx] > thr:
            last_idx = idx
            break

    if first_idx is None or last_idx is None or last_idx < first_idx:
        return pcm16_bytes

    pad_frames = int((pad_ms / frame_ms)) if frame_ms > 0 else 0
    start_frame = max(0, first_idx - pad_frames)
    end_frame = min(len(rms) - 1, last_idx + pad_frames)

    start_sample = start_frame * frame_samples
    end_sample = min(total, (end_frame + 1) * frame_samples)

    # Safety caps (do not remove more than configured maximums).
    max_lead_samples = int(max(0.0, max_leading_s) * sample_rate)
    max_tail_samples = int(max(0.0, max_trailing_s) * sample_rate)

    start_sample = min(start_sample, max_lead_samples)
    if total - end_sample > max_tail_samples:
        end_sample = total - max_tail_samples

    if end_sample <= start_sample:
        return pcm16_bytes

    trimmed = samples[start_sample:end_sample]
    if sys.byteorder != "little":
        trimmed.byteswap()
    return trimmed.tobytes()


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


