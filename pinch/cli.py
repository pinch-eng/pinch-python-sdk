from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import TextIO

from .audio import (
    iter_pcm_frames,
    realtime_sleep,
    wav_to_pcm16_mono_16k,
    write_wav,
)
from .client import PinchClient
from .config import resolve_api_key, write_dotenv_api_key
from .errors import PinchError, PinchProtocolError
from .session import SessionParams


def _setup_logging(debug: bool) -> None:
    logger = logging.getLogger("pinch")
    logger.handlers.clear()
    if not debug:
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.CRITICAL)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def _next_results_out_paths(*, directory: Path) -> tuple[Path, Path]:
    """
    Pick the next available output paths under `directory` without overwriting.
    Returns (wav_path, transcript_path).
    """
    directory.mkdir(parents=True, exist_ok=True)
    for i in range(1, 10_000):
        stem = "output" if i == 1 else f"output{i}"
        wav_path = directory / f"{stem}.wav"
        txt_path = directory / f"{stem}.txt"
        if not wav_path.exists() and not txt_path.exists():
            return wav_path, txt_path
    raise PinchProtocolError("Unable to select an output filename. Please clear the results folder and try again.")


def _coerce_transcript_path(out_path: str) -> Path:
    """
    Treat `--out` as a transcript file path.
    - If the user passes a path with a non-.txt suffix (or .wav), rewrite to .txt.
    - If the user passes a directory, create an output*.txt file inside it.
    """
    p = Path(out_path)
    # Best-effort: if they passed an existing directory, write into it.
    if p.exists() and p.is_dir():
        _, txt = _next_results_out_paths(directory=p)
        return txt
    # If it looks like a directory path (ends with a separator), also treat as dir.
    if str(out_path).endswith(("/", "\\")):
        p.mkdir(parents=True, exist_ok=True)
        _, txt = _next_results_out_paths(directory=p)
        return txt
    # Ensure .txt extension.
    if p.suffix.lower() != ".txt":
        return p.with_suffix(".txt")
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pinch",
        description="Pinch real-time speech translation",
    )
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("configure", help="Save PINCH_API_KEY to a local .env file")
    c.add_argument("--debug", action="store_true", help="Enable debug logs")

    t = sub.add_parser(
        "translate",
        help="Start a translation session",
        epilog=(
            "Examples:\n"
            "  pinch translate --in examples/input.wav --out output.wav\n"
            "  pinch translate --input examples/input.wav --output output.wav\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    t.add_argument("--source", default="en-US", help="Source language (default: en-US)")
    t.add_argument("--target", default="es-ES", help="Target language (default: es-ES)")
    t.add_argument("--voice", default="clone", help="Voice type: clone, male, female")
    t.add_argument("--debug", action="store_true", help="Enable debug logs")

    t.add_argument("--in", "--input", dest="in_path", required=True, help="Input WAV path")

    t.add_argument(
        "--out",
        "--output",
        dest="out_path",
        help=(
            "Output path. Default: ./results/output*.wav (+ sibling .txt). "
            "With --no-audio, this is treated as the transcript .txt path."
        ),
    )

    # Audio output is enabled by default; allow transcript-only runs with --no-audio.
    t.add_argument(
        "--no-audio",
        dest="audio_enabled",
        action="store_false",
        help="Transcript-only mode (no output WAV).",
    )
    t.set_defaults(audio_enabled=True)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(bool(getattr(args, "debug", False)))

    try:
        if args.command == "configure":
            return _cmd_configure()
        if args.command == "translate":
            return _cmd_translate(args)
        return 2
    except PinchError as e:
        print(str(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def _cmd_configure() -> int:
    api_key = resolve_api_key(None, prompt_if_missing=True, offer_write_dotenv=False, interactive=True)
    path = write_dotenv_api_key(api_key, directory=Path.cwd())
    print(f"Saved PINCH_API_KEY to {path.name}")
    return 0


def _cmd_translate(args: argparse.Namespace) -> int:
    transcript_path: Path | None = None
    if args.audio_enabled:
        if not args.out_path:
            wav_path, txt_path = _next_results_out_paths(directory=Path.cwd() / "results")
            args.out_path = str(wav_path)
            transcript_path = txt_path
    else:
        # Transcript-only mode: do not write output WAV. Treat --out as transcript path.
        if args.out_path:
            transcript_path = _coerce_transcript_path(args.out_path)
        else:
            _, transcript_path = _next_results_out_paths(directory=Path.cwd() / "results")
        args.out_path = None

    params = SessionParams(
        source_language=args.source,
        target_language=args.target,
        voice_type=args.voice,
        audio_output_enabled=bool(args.audio_enabled),
    )

    client = PinchClient()
    session = client.create_session(params)

    try:
        asyncio.run(
            _run_translation(
                client=client,
                session=session,
                params=params,
                in_path=args.in_path,
                out_path=args.out_path,
                transcript_path=transcript_path,
                audio_enabled=bool(args.audio_enabled),
            )
        )
        return 0
    except KeyboardInterrupt:
        return 130


async def _run_translation(
    *,
    client: PinchClient,
    session,
    params: SessionParams,
    in_path: str | None,
    out_path: str | None,
    transcript_path: Path | None,
    audio_enabled: bool,
) -> None:
    stream = await client.connect_stream(session, audio_output_enabled=audio_enabled)

    audio_bytes = bytearray()
    out_sr: int | None = None
    out_ch: int | None = None

    loop = asyncio.get_running_loop()
    last_audio_t = loop.time()
    last_transcript_t = loop.time()
    saw_transcript = False

    transcript_file: TextIO | None = None
    if out_path and transcript_path is None:
        transcript_path = Path(out_path).with_suffix(".txt")

    async def consume() -> None:
        nonlocal out_sr, out_ch, last_audio_t, last_transcript_t, saw_transcript
        async with stream:
            async for ev in stream.events():
                if ev.type == "transcript":
                    last_transcript_t = loop.time()
                    saw_transcript = True
                    prefix = "ORIG" if ev.kind == "original" else "TRAN"
                    line = f"{prefix}: {ev.text}"
                    print(line, flush=True)
                    if transcript_file is not None:
                        try:
                            transcript_file.write(line + "\n")
                            transcript_file.flush()
                        except Exception:
                            # Best-effort; keep CLI output flowing.
                            pass
                elif ev.type == "audio" and audio_enabled:
                    last_audio_t = loop.time()
                    if out_sr is None:
                        out_sr = ev.sample_rate
                        out_ch = ev.channels
                    audio_bytes.extend(ev.pcm16_bytes)

    async def produce() -> None:
        if not in_path:
            return
        pcm = wav_to_pcm16_mono_16k(in_path)
        with realtime_sleep(20) as tick:
            for chunk in iter_pcm_frames(pcm, sample_rate=16000, channels=1, frame_ms=20):
                await stream.send_pcm16(chunk, sample_rate=16000, channels=1)
                tick()
        done_t = loop.time()
        # Tail window: transcripts may arrive after input ends (especially in --no-audio mode).
        min_tail_s = 6.0 if audio_enabled else 10.0
        max_tail_s = 20.0
        min_deadline = done_t + min_tail_s
        max_deadline = done_t + max_tail_s
        while True:
            now = loop.time()
            if now >= max_deadline:
                break
            # In audio mode, wait for audio frames to go quiet; in --no-audio mode, wait for transcripts.
            if audio_enabled:
                if now >= min_deadline and (now - last_audio_t) >= 2.0:
                    break
            else:
                # Wait for at least one transcript (best-effort) and then for a quiet window.
                if now >= min_deadline and saw_transcript and (now - last_transcript_t) >= 2.0:
                    break
            await asyncio.sleep(0.2)
        await stream.aclose()

    consumer_task = asyncio.create_task(consume())
    producer_task = asyncio.create_task(produce())
    try:
        if transcript_path is not None:
            transcript_file = transcript_path.open("w", encoding="utf-8")
        try:
            await asyncio.gather(consumer_task, producer_task)
        except asyncio.CancelledError:
            # Ctrl+C (SIGINT) typically cancels the main task. Finalize and write output files.
            for t in (producer_task, consumer_task):
                t.cancel()
            await asyncio.gather(producer_task, consumer_task, return_exceptions=True)
            try:
                await stream.aclose()
            except Exception:
                pass
    finally:
        if transcript_file is not None:
            try:
                transcript_file.close()
            except Exception:
                pass

    if audio_enabled and out_path:
        if out_sr is None or out_ch is None or not audio_bytes:
            raise PinchProtocolError("No translated audio was received; cannot create an output audio file.")
        write_wav(out_path, pcm16_bytes=bytes(audio_bytes), sample_rate=out_sr, channels=out_ch)


