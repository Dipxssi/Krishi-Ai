"""LLM wrapper — Groq for text generation.

Agents must call this module, not provider SDKs directly.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_groq_client = None


def _has_key(value: str | None) -> bool:
    return bool(value and value.strip())


def _get_groq_client():
    global _groq_client
    settings = get_settings()
    if not _has_key(settings.groq_api_key):
        return None
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=settings.groq_api_key.strip(), timeout=30.0, max_retries=1)
    return _groq_client


def is_llm_available() -> bool:
    return _has_key(get_settings().groq_api_key)


def generate(prompt: str, system: str | None = None) -> str | None:
    """Return text from Groq, or None if unavailable or all model calls fail."""
    client = _get_groq_client()
    if client is None:
        return None
    settings = get_settings()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Candidate models in order of priority; ensures resilience against model decommission/404
    models_to_try: list[str] = [settings.groq_model]
    for fallback in ("qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    for model in models_to_try:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
                max_tokens=750,
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("Groq generate failed with model %s: %s", model, exc)
            continue
    return None
