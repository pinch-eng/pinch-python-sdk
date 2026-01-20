from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .config import resolve_api_key
from .errors import PinchConfigError, PinchNetworkError, PinchValidationError, map_http_error
from .session import SessionInfo, SessionParams
from .stream import PinchStream


class PinchClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base_url: str = "https://api.startpinch.com",
        timeout_s: float = 30.0,
    ) -> None:
        self._api_key = resolve_api_key(api_key, prompt_if_missing=True, offer_write_dotenv=True)
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_s = float(timeout_s)

    def create_session(self, params: Optional[SessionParams] = None) -> SessionInfo:
        params = params or SessionParams()
        params.validate()

        try:
            import httpx  # type: ignore
        except Exception as e:  # pragma: no cover
            raise PinchConfigError(
                "HTTP dependencies are missing. Install the 'httpx' package to continue."
            ) from e

        url = f"{self._api_base_url}/api/beta1/session"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "sourceLanguage": params.source_language,
            "targetLanguage": params.target_language,
            "voiceType": params.voice_type,
        }

        try:
            with httpx.Client(timeout=self._timeout_s) as client:
                def _post(req_body: dict) -> tuple["httpx.Response", Optional[object]]:
                    r = client.post(url, headers=headers, json=req_body)
                    try:
                        return r, r.json()
                    except Exception:
                        return r, None

                resp, payload = _post(body)

                # No fallback: if the service rejects clone, instruct the user to try male/female.
                if resp.status_code == 400 and params.voice_type == "clone":
                    err = payload.get("error") if isinstance(payload, dict) else None
                    if isinstance(err, str) and (
                        ("Invalid voiceType" in err) or ("voiceId is required" in err)
                    ):
                        raise PinchValidationError(
                            "Error: acceptable voice types are clone, male, female. clone is not working, so try male or female."
                        )
        except (httpx.TimeoutException, httpx.NetworkError) as e:
            raise PinchNetworkError("Network error. Please check your connection and try again.") from e

        if resp.status_code >= 400:
            raise map_http_error(resp.status_code, payload)

        return SessionInfo.from_response(payload)

    async def connect_stream(
        self,
        session: SessionInfo,
        *,
        audio_output_enabled: bool = True,
    ) -> PinchStream:
        stream = PinchStream(session=session, audio_output_enabled=audio_output_enabled)
        await stream.connect()
        return stream

    async def translate_file(
        self,
        *,
        input_wav_path: Union[str, Path],
        output_wav_path: Union[str, Path],
        transcript_path: Union[str, Path],
        source_language: str = "en-US",
        target_language: str = "es-ES",
        audio_output_enabled: bool = True,
    ) -> "FileTranslateResult":
        """
        Convenience wrapper: translate a WAV file and write outputs.

        This delegates to the existing top-level file helper (which performs streaming internally).
        """
        # Import lazily to avoid circular imports.
        from .file_translate import translate_file as _translate_file

        return await _translate_file(
            input_wav_path=input_wav_path,
            output_wav_path=output_wav_path,
            transcript_path=transcript_path,
            source_language=source_language,
            target_language=target_language,
            audio_output_enabled=audio_output_enabled,
            api_key=self._api_key,
            api_base_url=self._api_base_url,
            timeout_s=self._timeout_s,
        )


