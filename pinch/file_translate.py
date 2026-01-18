from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional, Union

from .audio import (
    iter_pcm_frames,
    realtime_sleep,
    trim_pcm16_silence,
    wav_to_pcm16_mono_supported,
    write_wav,
)
from .client import PinchClient
from .errors import PinchProtocolError
from .session import SessionParams


TranscriptMode = Literal["headings", "lines"]


@dataclass(frozen=True)
class FileTranslateResult:
    output_wav_path: Path
    transcript_path: Path
    original_transcript: str
    translated_transcript: str


def _dedupe_append(lines: list[str], text: str) -> None:
    t = (text or "").strip()
    if not t:
        return
    if lines and lines[-1] == t:
        return
    lines.append(t)


def _format_transcript_file(*, original: Optional[str], translated: Optional[str]) -> str:
    o = (original or "").strip() or "(unavailable)"
    t = (translated or "").strip() or "(unavailable)"
    return f"ORIGINAL TRANSCRIPT\n{o}\n\nTRANSLATED TRANSCRIPT\n{t}\n"


async def translate_file(
    *,
    input_wav_path: Union[str, Path],
    output_wav_path: Union[str, Path],
    transcript_path: Union[str, Path],
    source_language: str = "en-US",
    target_language: str = "es-ES",
    audio_output_enabled: bool = True,
    api_key: Optional[str] = None,
    api_base_url: str = "https://api.startpinch.com",
    timeout_s: float = 30.0,
) -> FileTranslateResult:
    """
    Translate a WAV file using Pinch and write:
    - translated audio to `output_wav_path`
    - transcripts to `transcript_path`

    Notes:
    - `voiceType` is ALWAYS "clone" (hardcoded, not configurable here).
    - Transcript content is never printed to stdout.
    """
    return await _translate_file_advanced(
        input_wav_path=input_wav_path,
        output_wav_path=output_wav_path,
        transcript_path=transcript_path,
        source_language=source_language,
        target_language=target_language,
        voice_type="clone",
        audio_output_enabled=audio_output_enabled,
        api_key=api_key,
        api_base_url=api_base_url,
        timeout_s=timeout_s,
        print_transcripts=False,
        transcript_mode="headings",
    )


async def _translate_file_advanced(
    *,
    input_wav_path: Union[str, Path],
    output_wav_path: Union[str, Path],
    transcript_path: Union[str, Path],
    source_language: str,
    target_language: str,
    voice_type: str,
    audio_output_enabled: bool,
    api_key: Optional[str],
    api_base_url: str,
    timeout_s: float,
    print_transcripts: bool,
    transcript_mode: TranscriptMode,
) -> FileTranslateResult:
    in_path = Path(input_wav_path)
    out_wav = Path(output_wav_path)
    out_txt = Path(transcript_path)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    params = SessionParams(
        source_language=source_language,
        target_language=target_language,
        voice_type=voice_type,
        audio_output_enabled=bool(audio_output_enabled),
    )

    # Note: create_session must be called with a SessionParams object positionally.
    client = PinchClient(api_key=api_key, api_base_url=api_base_url, timeout_s=timeout_s)
    session = client.create_session(params)
    stream = await client.connect_stream(session, audio_output_enabled=bool(audio_output_enabled))

    audio_bytes = bytearray()
    out_sr: Optional[int] = None
    out_ch: Optional[int] = None

    loop = asyncio.get_running_loop()
    last_audio_t = loop.time()
    last_transcript_t = loop.time()

    original_final: list[str] = []
    translated_final: list[str] = []
    original_partial: Optional[str] = None
    translated_partial: Optional[str] = None
    saw_any_transcript = False

    async def consume() -> None:
        nonlocal out_sr, out_ch, last_audio_t, last_transcript_t
        nonlocal original_partial, translated_partial, saw_any_transcript
        async with stream:
            async for ev in stream.events():
                if ev.type == "transcript":
                    last_transcript_t = loop.time()
                    saw_any_transcript = True

                    if transcript_mode == "lines" and print_transcripts:
                        prefix = "ORIG" if ev.kind == "original" else "TRAN"
                        print(f"{prefix}: {ev.text}", flush=True)

                    if ev.kind == "original":
                        if ev.is_final is False:
                            original_partial = ev.text
                        else:
                            _dedupe_append(original_final, ev.text)
                    else:
                        if ev.is_final is False:
                            translated_partial = ev.text
                        else:
                            _dedupe_append(translated_final, ev.text)

                elif ev.type == "audio" and audio_output_enabled:
                    last_audio_t = loop.time()
                    if out_sr is None:
                        out_sr = ev.sample_rate
                        out_ch = ev.channels
                    audio_bytes.extend(ev.pcm16_bytes)

    async def produce() -> None:
        input_sr, pcm = wav_to_pcm16_mono_supported(in_path)
        with realtime_sleep(20) as tick:
            for chunk in iter_pcm_frames(pcm, sample_rate=input_sr, channels=1, frame_ms=20):
                await stream.send_pcm16(chunk, sample_rate=input_sr, channels=1)
                tick()

        done_t = loop.time()
        # Tail window: allow transcripts/audio to arrive after input ends.
        min_tail_s = 6.0 if audio_output_enabled else 10.0
        max_tail_s = 20.0
        min_deadline = done_t + min_tail_s
        max_deadline = done_t + max_tail_s

        while True:
            now = loop.time()
            if now >= max_deadline:
                break

            if audio_output_enabled:
                # Stop after a short quiet window post-min-deadline.
                if now >= min_deadline and (now - last_audio_t) >= 2.0:
                    break
            else:
                if now >= min_deadline and saw_any_transcript and (now - last_transcript_t) >= 2.0:
                    break

            await asyncio.sleep(0.2)

        await stream.aclose()

    consumer_task = asyncio.create_task(consume())
    producer_task = asyncio.create_task(produce())
    try:
        await asyncio.gather(consumer_task, producer_task)
    except asyncio.CancelledError:
        for t in (producer_task, consumer_task):
            t.cancel()
        await asyncio.gather(producer_task, consumer_task, return_exceptions=True)
        try:
            await stream.aclose()
        except Exception:
            pass

    original_text = "\n".join(original_final).strip() if original_final else (original_partial or "(unavailable)")
    translated_text = (
        "\n".join(translated_final).strip() if translated_final else (translated_partial or "(unavailable)")
    )

    # Always write a transcript file (even if transcripts are unavailable).
    if transcript_mode == "headings":
        out_txt.write_text(
            _format_transcript_file(original=original_text, translated=translated_text),
            encoding="utf-8",
        )
    else:
        # Alternate format (one line per transcript kind); still always write a file.
        out_txt.write_text(
            "\n".join([f"ORIG: {original_text}", f"TRAN: {translated_text}"]).strip() + "\n",
            encoding="utf-8",
        )

    if audio_output_enabled:
        if out_sr is None or out_ch is None or not audio_bytes:
            raise PinchProtocolError("No translated audio was received; cannot create an output audio file.")
        pcm = bytes(audio_bytes)
        trimmed = trim_pcm16_silence(
            pcm,
            sample_rate=out_sr,
            channels=out_ch,
            max_leading_s=5.0,
            max_trailing_s=10.0,
            pad_ms=100,
        )
        write_wav(out_wav, pcm16_bytes=trimmed or pcm, sample_rate=out_sr, channels=out_ch)

    return FileTranslateResult(
        output_wav_path=out_wav,
        transcript_path=out_txt,
        original_transcript=original_text,
        translated_transcript=translated_text,
    )

