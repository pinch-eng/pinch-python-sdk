from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Optional

from .errors import PinchConfigError, PinchProtocolError
from .events import AudioEvent, ErrorEvent, PinchEvent, SessionEnded, SessionStarted, TranscriptEvent
from .session import SessionInfo

def _safe_err(msg: str) -> ErrorEvent:
    return ErrorEvent(message=msg)


def _parse_transcript_payload(payload: Any) -> Optional[TranscriptEvent]:
    if not isinstance(payload, dict):
        return None
    t = payload.get("type")
    text = payload.get("text")
    is_final = payload.get("is_final")
    if not isinstance(t, str) or not isinstance(text, str):
        return None
    if t == "original_transcript":
        kind = "original"
    elif t == "translated_transcript":
        kind = "translated"
    else:
        return None
    if is_final is not None and not isinstance(is_final, bool):
        is_final = None
    return TranscriptEvent(kind=kind, text=text, is_final=is_final, raw=payload)


class PinchStream:
    """
    Async streaming connection.

    - Always supports transcript events (when they arrive).
    - Optionally yields translated audio frames when enabled.
    """

    def __init__(self, *, session: SessionInfo, audio_output_enabled: bool = True) -> None:
        self._session = session
        self._audio_output_enabled = bool(audio_output_enabled)

        self._room = None
        self._audio_source = None
        self._local_track = None
        self._tasks: set[asyncio.Task[None]] = set()
        self._events: "asyncio.Queue[PinchEvent]" = asyncio.Queue()
        self._closed = False
        self._connected = False
        self._selected_remote_audio_track = None
        self._audio_candidates: list[tuple[Any, Any, Any]] = []
        self._audio_fallback_task: Optional[asyncio.Task[None]] = None

    async def connect(self) -> None:
        if self._connected:
            return

        try:
            from livekit import rtc  # type: ignore
        except Exception as e:  # pragma: no cover
            raise PinchConfigError(
                "Streaming dependencies are missing. Please reinstall the Pinch SDK with required dependencies."
            ) from e

        self._room = rtc.Room()

        # Register transcript (data) handling, supporting common callback shapes.
        self._register_data_handler()
        self._register_track_handlers()

        try:
            await self._room.connect(self._session.url, self._session.token)
        except Exception as e:  # pragma: no cover
            # Keep message generic and safe.
            raise PinchProtocolError("Unable to start the session. Please try again.") from e

        self._connected = True
        await self._events.put(SessionStarted())

        # Input audio track is created lazily on first send_pcm16() so we can match
        # the actual input sample rate (e.g., 16kHz or 48kHz).
        self._audio_source = None
        self._local_track = None

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True

        for t in list(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        try:
            if self._room is not None:
                await self._room.disconnect()
        except Exception:
            pass

        await self._events.put(SessionEnded())

    async def __aenter__(self) -> "PinchStream":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def send_pcm16(self, pcm16_bytes: bytes, *, sample_rate: int, channels: int = 1) -> None:
        """
        Send PCM16 little-endian audio bytes to the session.

        Minimal constraints:
        - mono only (channels=1)
        - 16000 Hz recommended
        """
        if not pcm16_bytes:
            return
        if channels != 1:
            raise PinchProtocolError("Only mono audio is supported.")
        if sample_rate not in (16000, 48000):
            raise PinchProtocolError(
                "Unsupported input sample rate. Please provide 16000 Hz (recommended) or 48000 Hz audio."
            )

        try:
            from livekit import rtc  # type: ignore
        except Exception:  # pragma: no cover
            return

        # Lazily create the input audio source/track so the AudioSource matches the
        # sample rate of the frames we send (LiveKit requires this).
        if self._audio_source is None or self._local_track is None:
            try:
                if self._room is None or not self._connected:
                    return
                self._audio_source = rtc.AudioSource(sample_rate=sample_rate, num_channels=channels)
                self._local_track = rtc.LocalAudioTrack.create_audio_track("input-audio", self._audio_source)
                await self._room.local_participant.publish_track(self._local_track)
            except Exception:
                # If publish fails, transcripts can still work.
                self._audio_source = None
                self._local_track = None
                return

        # LiveKit expects PCM16 samples. Convert bytes -> AudioFrame.
        samples_per_channel = len(pcm16_bytes) // 2
        frame = rtc.AudioFrame(
            data=pcm16_bytes,
            sample_rate=sample_rate,
            num_channels=channels,
            samples_per_channel=samples_per_channel,
        )
        await self._audio_source.capture_frame(frame)

    async def events(self) -> AsyncIterator[PinchEvent]:
        """
        Async iterator of events (transcripts always; audio frames if enabled and available).
        """
        if not self._connected:
            await self.connect()
        while True:
            ev = await self._events.get()
            yield ev
            if ev.type == "session_ended":
                break

    # ---- internal wiring ----

    def _register_data_handler(self) -> None:
        room = self._room
        if room is None:
            return

        # Preferred: event emitter style "data_received".
        try:
            on = getattr(room, "on", None)
            if callable(on):

                @on("data_received")
                def _on_data(payload: Any, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
                    self._handle_data(payload)

                return
        except Exception:
            pass

        # Fallback: attribute assignment style.
        for attr in ("on_data_received", "on_data"):
            try:
                if hasattr(room, attr):
                    setattr(room, attr, lambda payload, *a, **k: self._handle_data(payload))
                    return
            except Exception:
                continue

    def _handle_data(self, payload: Any) -> None:
        # payload may be bytes/str/json;
        obj: Any = None
        try:
            data_field = getattr(payload, "data", None)
            if isinstance(data_field, (bytes, bytearray)):
                obj = json.loads(bytes(data_field).decode("utf-8", errors="ignore"))
            elif isinstance(payload, (bytes, bytearray)):
                obj = json.loads(payload.decode("utf-8", errors="ignore"))
            elif isinstance(payload, str):
                obj = json.loads(payload)
            elif isinstance(payload, dict):
                obj = payload
        except Exception:
            return

        ev = _parse_transcript_payload(obj)
        if ev is None:
            return

        try:
            self._events.put_nowait(ev)
        except Exception:
            pass

    def _register_track_handlers(self) -> None:
        room = self._room
        if room is None:
            return

        try:
            on = getattr(room, "on", None)
            if callable(on):

                @on("track_subscribed")
                def _on_track(track: Any, publication: Any, participant: Any) -> None:  
                    self._maybe_start_audio(track, publication, participant)

                return
        except Exception:
            pass

    def _maybe_start_audio(self, track: Any, publication: Any, participant: Any) -> None:
        if not self._audio_output_enabled:
            return
        if self._selected_remote_audio_track is not None:
            return

        # Identify the best track using internal heuristics.
        identity = getattr(participant, "identity", None)
        name = getattr(publication, "name", None) or getattr(track, "name", None)
        kind = getattr(track, "kind", None)

        # Prefer known defaults; else fallback.
        preferred = (identity == "translation-agent") and (name == "translated-audio")
        contains_translated = isinstance(name, str) and ("translated" in name.lower())

        is_audio = False
        try:
            # livekit.rtc.TrackKind.AUDIO may exist
            from livekit import rtc  # type: ignore

            is_audio = kind == getattr(rtc.TrackKind, "AUDIO", None) or track.__class__.__name__.lower().find("audio") >= 0
        except Exception:  # pragma: no cover
            is_audio = track.__class__.__name__.lower().find("audio") >= 0

        if not is_audio:
            return

        # Prefer known defaults, then heuristics; otherwise keep as candidate and fallback later.
        if preferred or (identity == "translation-agent") or contains_translated:
            self._selected_remote_audio_track = track
            self._start_audio_task(track)
            return

        self._audio_candidates.append((track, publication, participant))
        if self._audio_fallback_task is None:
            self._audio_fallback_task = asyncio.create_task(self._select_audio_fallback())
            self._audio_fallback_task.add_done_callback(lambda t: setattr(self, "_audio_fallback_task", None))

    async def _select_audio_fallback(self) -> None:
        # Wait briefly for a better match to arrive.
        try:
            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            return
        if not self._audio_output_enabled:
            return
        if self._selected_remote_audio_track is not None:
            return
        if not self._audio_candidates:
            return
        track, _, _ = self._audio_candidates[0]
        self._selected_remote_audio_track = track
        self._start_audio_task(track)

    def _start_audio_task(self, track: Any) -> None:
        async def _run() -> None:
            try:
                # Prefer rtc.AudioStream if available.
                from livekit import rtc  # type: ignore

                audio_stream = getattr(rtc, "AudioStream", None)
                if audio_stream is None:
                    return
                stream = audio_stream(track)
                async for evt in stream:
                    frame = getattr(evt, "frame", None)
                    if frame is None:
                        continue
                    # frame.data is a memoryview of int16 samples; convert to PCM16 bytes
                    mv = getattr(frame, "data", None)
                    if mv is None:
                        continue
                    pcm16 = mv.tobytes() if hasattr(mv, "tobytes") else bytes(mv)
                    sample_rate = int(getattr(frame, "sample_rate", 48000))
                    channels = int(getattr(frame, "num_channels", 1))
                    await self._events.put(
                        AudioEvent(pcm16_bytes=pcm16, sample_rate=sample_rate, channels=channels)
                    )
            except asyncio.CancelledError:
                return
            except Exception:
                await self._events.put(_safe_err("Audio output is unavailable in this session."))

        task = asyncio.create_task(_run())
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.discard(t))


