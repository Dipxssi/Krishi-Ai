"""Voice input layer (Phase 5) — stub STT; swap Whisper when deployed."""

from __future__ import annotations

import base64

from fastapi import APIRouter

from app.schemas.models import VoiceTranscribeRequest, VoiceTranscribeResponse
from app.services.crop_registry import normalize_crop_name

router = APIRouter(prefix="/voice", tags=["voice"])

_CROP_WORDS = {
    "tomato": "tomato",
    "tomatoes": "tomato",
    "potato": "potato",
    "potatoes": "potato",
    "maize": "maize",
    "corn": "maize",
    "wheat": "wheat",
    "rice": "rice",
    "paddy": "rice",
    "onion": "onion",
    "cotton": "cotton",
}


@router.post("/transcribe", response_model=VoiceTranscribeResponse)
def transcribe(request: VoiceTranscribeRequest):
    # V1 stub: decode payload size check only; production should call Whisper/OpenAI STT.
    try:
        raw = base64.b64decode(request.audio_base64.split(",", 1)[-1])
    except Exception:
        raw = b""
    if len(raw) < 16:
        return VoiceTranscribeResponse(
            text="",
            note="Audio too short or invalid. Send base64 WAV/WEBM with farmer speech.",
        )
    return VoiceTranscribeResponse(
        text="[voice stub] Please type your question in the Ask tab until Whisper STT is configured.",
        normalized_crop=None,
        note=f"Received {len(raw)} bytes audio. Configure Whisper API for real transcription.",
    )


@router.post("/normalize-crop")
def normalize_crop_name_endpoint(crop: str):
    return {"crop_id": normalize_crop_name(crop) or _CROP_WORDS.get(crop.lower())}
