"""LLM wrapper — Groq first for generation, Gemini as fallback.

Embeddings stay on Gemini (Groq does not provide an embedding API).
Agents must call this module, not provider SDKs directly.
"""

from __future__ import annotations

import logging
from typing import Sequence

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_groq_client = None
_gemini_client = None


def _has_key(value: str | None) -> bool:
    return bool(value and value.strip())


def _get_groq_client():
    global _groq_client
    settings = get_settings()
    if not _has_key(settings.groq_api_key):
        return None
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=settings.groq_api_key.strip(), timeout=30.0)
    return _groq_client


def _get_gemini_client():
    global _gemini_client
    settings = get_settings()
    if not _has_key(settings.gemini_api_key):
        return None
    if _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(
            api_key=settings.gemini_api_key.strip(),
            http_options={"timeout": 30_000},
        )
    return _gemini_client


def is_llm_available() -> bool:
    settings = get_settings()
    return _has_key(settings.groq_api_key) or _has_key(settings.gemini_api_key)


def _generate_groq(prompt: str, system: str | None = None) -> str | None:
    client = _get_groq_client()
    if client is None:
        return None
    settings = get_settings()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        text = (response.choices[0].message.content or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq generate failed, falling back to Gemini: %s", exc)
        return None


def _generate_gemini(prompt: str, system: str | None = None) -> str | None:
    client = _get_gemini_client()
    if client is None:
        return None
    settings = get_settings()
    try:
        from google.genai import types

        contents = f"{system}\n\n{prompt}" if system else prompt
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


def generate(prompt: str, system: str | None = None) -> str | None:
    """Return text from Groq, or Gemini if Groq is missing/fails, else None."""
    text = _generate_groq(prompt, system)
    if text:
        return text
    return _generate_gemini(prompt, system)


def embed(texts: Sequence[str]) -> list[list[float]] | None:
    """Embed texts with Gemini; return None if unavailable."""
    client = _get_gemini_client()
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
