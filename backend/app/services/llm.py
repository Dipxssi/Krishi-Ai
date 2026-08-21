"""Gemini LLM wrapper — agents must call this, not the SDK directly."""

from __future__ import annotations

import logging
from typing import Sequence

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    settings = get_settings()
    if not settings.gemini_api_key or not settings.gemini_api_key.strip():
        return None
    if _client is None:
        from google import genai

        _client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options={"timeout": 30_000},
        )
    return _client


def is_llm_available() -> bool:
    key = get_settings().gemini_api_key
    return bool(key and key.strip())


def generate(prompt: str, system: str | None = None) -> str | None:
    """Return Gemini text, or None if no API key / call fails."""
    client = _get_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        from google.genai import types

        contents = prompt
        if system:
            contents = f"{system}\n\n{prompt}"
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=contents,
            config=types.GenerateContentConfig(
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )
        return (response.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini generate failed: %s", exc)
        return None


def embed(texts: Sequence[str]) -> list[list[float]] | None:
    """Embed texts with Gemini; return None if unavailable."""
    client = _get_client()
    if client is None or not texts:
        return None
    settings = get_settings()
    try:
        vectors: list[list[float]] = []
        for text in texts:
            result = client.models.embed_content(
                model=settings.gemini_embedding_model,
                contents=text,
            )
            # google-genai returns embeddings on result.embeddings or result.embedding
            if hasattr(result, "embeddings") and result.embeddings:
                emb0 = result.embeddings[0]
                values = emb0.values if hasattr(emb0, "values") else emb0
                vectors.append(list(values))
            elif hasattr(result, "embedding") and result.embedding is not None:
                emb = result.embedding
                values = emb.values if hasattr(emb, "values") else emb
                vectors.append(list(values))
            else:
                return None
        return vectors
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini embed failed: %s", exc)
        return None
