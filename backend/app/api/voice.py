"""Speech conversion endpoints. Chat answers still flow through POST /query."""

from __future__ import annotations

import base64
import binascii
import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.config import get_settings
from app.db.users import UserRow
from app.schemas.models import (
    VoiceSpeechRequest,
    VoiceTranscribeRequest,
    VoiceTranscribeResponse,
)
from app.services.auth_service import get_current_user
from app.services.crop_registry import normalize_crop_name

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])
MAX_AUDIO_BYTES = 25 * 1024 * 1024
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(?:sk|gsk|sess|rk)[-_][A-Za-z0-9_-]{8,}\b|\bBearer\s+[A-Za-z0-9._~-]+"
)
_NAMED_SECRET_RE = re.compile(
    r"(?i)(api[_ -]?key|authorization|access[_ -]?token)(\s*[:=]\s*)[^\s,;]+"
)


class AudioResponse(Response):
    media_type = "audio/wav"


_ORPHEUS_MAX_CHARS = 200
_INDIC_RE = re.compile(r"[\u0900-\u097F\u0C80-\u0CFF]")


def _spoken_english_for_tts(raw: str) -> str:
    """Groq Orpheus is English-only and capped at 200 chars — summarize if needed."""
    cleaned = " ".join((raw or "").split())
    if not cleaned:
        return "No advice to read."

    needs_summary = bool(_INDIC_RE.search(cleaned)) or len(cleaned) > _ORPHEUS_MAX_CHARS
    if needs_summary:
        from app.services import llm

        prompt = (
            "Rewrite the following farm advice as a short spoken English summary "
            f"for a farmer. Max {_ORPHEUS_MAX_CHARS - 20} characters. "
            "No markdown, no bullet lists, plain sentences only.\n\n"
            f"{cleaned[:3000]}"
        )
        summary = llm.generate(
            prompt,
            system="You convert crop advice into brief clear spoken English.",
        )
        if summary:
            cleaned = " ".join(summary.split())

    if len(cleaned) > _ORPHEUS_MAX_CHARS:
        cleaned = cleaned[: _ORPHEUS_MAX_CHARS - 1].rsplit(" ", 1)[0] + "…"
    return cleaned or "Please review the on-screen advice."


def _provider_error_message(response: httpx.Response) -> str:
    """Extract a useful provider diagnostic while redacting credential-like values."""
    try:
        payload = response.json()
    except ValueError:
        payload = {"message": response.text}

    error = payload.get("error", payload) if isinstance(payload, dict) else payload
    if isinstance(error, dict):
        detail = " | ".join(
            str(error[key])
            for key in ("type", "code", "message")
            if error.get(key) is not None
        )
    else:
        detail = str(error)
    detail = _NAMED_SECRET_RE.sub(r"\1\2[REDACTED]", detail)
    detail = _SECRET_VALUE_RE.sub("[REDACTED]", detail)
    return " ".join(detail.split())[:1000] or "No provider error details returned."


_CROP_WORDS = {
    "tomato": "tomato", "tomatoes": "tomato", "potato": "potato",
    "potatoes": "potato", "maize": "maize", "corn": "maize",
    "wheat": "wheat", "rice": "rice", "paddy": "rice",
    "onion": "onion", "cotton": "cotton",
}


def _decode_audio(payload: str) -> bytes:
    encoded = payload.split(",", 1)[-1]
    if len(encoded) > ((MAX_AUDIO_BYTES + 2) // 3) * 4:
        raise HTTPException(status_code=413, detail="Audio must be 25 MB or smaller.")
    try:
        audio = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid base64 audio.") from exc
    if not audio:
        raise HTTPException(status_code=400, detail="Audio is empty.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio must be 25 MB or smaller.")
    return audio


@router.post("/transcribe", response_model=VoiceTranscribeResponse)
def transcribe(
    request: VoiceTranscribeRequest,
    _user: UserRow = Depends(get_current_user),
):
    from app.services.groq_keys import (
        has_groq_api_key,
        is_key_failover_error,
        iter_groq_api_keys_for_attempt,
    )

    if not has_groq_api_key():
        raise HTTPException(
            status_code=503,
            detail="Speech transcription is not configured (GROQ_API_KEY / GROQ_API_KEYS).",
        )
    audio = _decode_audio(request.audio_base64)
    if len(audio) < 16:
        raise HTTPException(status_code=400, detail="Audio is too short to transcribe.")
    if not request.content_type.lower().startswith("audio/"):
        raise HTTPException(status_code=400, detail="The uploaded recording must have an audio content type.")

    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", request.filename.replace("\\", "/").rsplit("/", 1)[-1])[:100]
    files = {"file": (safe_name or "recording.webm", audio, request.content_type)}
    # verbose_json includes the language Whisper thought it heard.
    data = {"model": "whisper-large-v3-turbo", "response_format": "verbose_json"}
    # Only pin Whisper for Indic languages. Forcing "en" (the farm-profile default)
    # makes Kannada/Hindi speech transcribe as English.
    pinned: str | None = None
    if request.language_hint:
        from app.services.multilingual import normalize_language_code
        lang_code = normalize_language_code(request.language_hint)
        if lang_code in ("kn", "hi"):
            pinned = lang_code
            data["language"] = lang_code

    from app.services.multilingual import (
        normalize_indic_script,
        prefer_indic_transcript,
        transcript_lacks_indic_script,
        transcript_needs_hindi_retry,
    )

    text = ""
    last_http_error: httpx.HTTPStatusError | None = None
    keys = list(iter_groq_api_keys_for_attempt())

    for key_index, api_key in enumerate(keys):
        headers = {"Authorization": f"Bearer {api_key}"}

        def _call(form: dict, *, _headers: dict[str, str] = headers) -> dict:
            result = httpx.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers=_headers,
                data=form,
                files=files,
                timeout=90.0,
            )
            result.raise_for_status()
            payload = result.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
                raise ValueError("Unexpected transcription response")
            return payload

        try:
            payload = _call(data)
            text = normalize_indic_script(payload["text"].strip())
            detected = payload.get("language") if isinstance(payload.get("language"), str) else None

            # 1) Icelandic/Latin garbage mis-ID of Hindi → force hi
            if pinned is None and transcript_needs_hindi_retry(text, detected):
                retry = _call({**data, "language": "hi"})
                retry_text = normalize_indic_script(retry["text"].strip())
                text = prefer_indic_transcript(text, retry_text)

            # 2) Hindi/Kannada speech auto-detected as English paraphrase
            #    ("What is the problem with this crop?") — recover Indic script.
            if pinned is None and transcript_lacks_indic_script(text):
                for force_lang in ("hi", "kn"):
                    retry = _call({**data, "language": force_lang})
                    retry_text = normalize_indic_script(retry["text"].strip())
                    improved = prefer_indic_transcript(text, retry_text)
                    if improved != text:
                        text = improved
                        logger.info(
                            "Recovered %s script after English/Latin Whisper auto-detect",
                            force_lang,
                        )
                        break
            elif pinned == "hi" and transcript_lacks_indic_script(text):
                # Pinned Hindi still returned Latin — one more forced hi pass is useless;
                # try without conflicting fields already set.
                pass
            break
        except httpx.HTTPStatusError as exc:
            last_http_error = exc
            logger.warning(
                "Groq transcription rejected key#%s/%s (HTTP %s)",
                key_index + 1,
                len(keys),
                exc.response.status_code,
            )
            if is_key_failover_error(exc) and key_index + 1 < len(keys):
                continue
            raise HTTPException(
                status_code=502,
                detail="Speech transcription provider rejected the audio.",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            logger.exception("Groq transcription request failed key#%s/%s", key_index + 1, len(keys))
            if is_key_failover_error(exc) and key_index + 1 < len(keys):
                continue
            raise HTTPException(
                status_code=502,
                detail="Speech transcription is temporarily unavailable.",
            ) from exc

    if not text:
        if last_http_error is not None:
            raise HTTPException(
                status_code=502,
                detail="Speech transcription provider rejected the audio.",
            ) from last_http_error
        raise HTTPException(status_code=422, detail="No speech was recognized. Please try again.")
    crop = next((canonical for word, canonical in _CROP_WORDS.items() if word in text.lower().split()), None)
    return VoiceTranscribeResponse(
        text=text,
        normalized_crop=normalize_crop_name(crop) if crop else None,
    )


@router.post(
    "/speech",
    response_class=AudioResponse,
    responses={200: {"content": {"audio/wav": {"schema": {"type": "string", "format": "binary"}}}}},
)
def synthesize_speech(
    request: VoiceSpeechRequest,
    _user: UserRow = Depends(get_current_user),
) -> AudioResponse:
    """TTS via Groq Orpheus (no OpenAI key). Hindi/Kannada text → short English spoken summary."""
    from app.services.groq_keys import (
        has_groq_api_key,
        is_key_failover_error,
        iter_groq_api_keys_for_attempt,
    )

    if not has_groq_api_key():
        raise HTTPException(
            status_code=503,
            detail="Speech playback is not configured (GROQ_API_KEY / GROQ_API_KEYS).",
        )

    settings = get_settings()
    spoken = _spoken_english_for_tts(request.text)
    # Map legacy OpenAI voice names to an Orpheus English voice.
    voice = request.voice.strip() if request.voice else settings.groq_tts_voice
    if voice.lower() in {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}:
        voice = settings.groq_tts_voice
    model = settings.groq_tts_model
    keys = list(iter_groq_api_keys_for_attempt())
    last_error: Exception | None = None

    for key_index, api_key in enumerate(keys):
        try:
            result = httpx.post(
                "https://api.groq.com/openai/v1/audio/speech",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "voice": voice,
                    "input": spoken,
                    "response_format": "wav",
                },
                timeout=90.0,
            )
            result.raise_for_status()
            if not result.content:
                raise HTTPException(status_code=502, detail="Speech provider returned empty audio.")
            return AudioResponse(content=result.content, media_type="audio/wav")
        except httpx.HTTPStatusError as exc:
            last_error = exc
            logger.warning(
                "Groq speech rejected key#%s/%s (HTTP %s): %s",
                key_index + 1,
                len(keys),
                exc.response.status_code,
                _provider_error_message(exc.response),
            )
            if is_key_failover_error(exc) and key_index + 1 < len(keys):
                continue
            raise HTTPException(
                status_code=502,
                detail="Speech playback provider rejected the request.",
            ) from exc
        except httpx.HTTPError as exc:
            last_error = exc
            logger.exception("Groq speech request failed key#%s/%s", key_index + 1, len(keys))
            if is_key_failover_error(exc) and key_index + 1 < len(keys):
                continue
            raise HTTPException(
                status_code=502,
                detail="Speech playback is temporarily unavailable.",
            ) from exc

    raise HTTPException(
        status_code=502,
        detail="Speech playback is temporarily unavailable.",
    ) from last_error


@router.post("/normalize-crop")
def normalize_crop_name_endpoint(
    crop: str,
    _user: UserRow = Depends(get_current_user),
):
    return {"crop_id": normalize_crop_name(crop) or _CROP_WORDS.get(crop.lower())}
