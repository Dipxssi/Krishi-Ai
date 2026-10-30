"""LLM wrapper — Groq for text generation.

Agents must call this module, not provider SDKs directly.
Supports multiple keys via GROQ_API_KEYS (comma-separated) + GROQ_API_KEY.
"""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.services.groq_keys import (
    has_groq_api_key,
    is_key_failover_error,
    iter_groq_api_keys_for_attempt,
)

logger = logging.getLogger(__name__)


def is_llm_available() -> bool:
    return has_groq_api_key()


def generate(prompt: str, system: str | None = None) -> str | None:
    """Return text from Groq, or None if unavailable or all model/key calls fail."""
    if not has_groq_api_key():
        return None

    from groq import Groq

    settings = get_settings()
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    models_to_try: list[str] = [settings.groq_model]
    for fallback in ("qwen/qwen3.8-27b", "openai/gpt-oss-20b"):
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    max_tokens = max(256, int(settings.groq_max_tokens or 2200))
    keys = list(iter_groq_api_keys_for_attempt())
    last_error: Exception | None = None

    for key_index, api_key in enumerate(keys):
        client = Groq(api_key=api_key, timeout=45.0, max_retries=0)
        key_label = f"key#{key_index + 1}/{len(keys)}"
        for model in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=max_tokens,
                )
                choice = response.choices[0]
                finish = getattr(choice, "finish_reason", None)
                text = (choice.message.content or "").strip()
                if finish and finish != "stop":
                    logger.warning(
                        "Groq generate truncated %s model=%s finish_reason=%s chars=%s max_tokens=%s",
                        key_label,
                        model,
                        finish,
                        len(text),
                        max_tokens,
                    )
                if text:
                    return text
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.warning(
                    "Groq generate failed %s model=%s: %s",
                    key_label,
                    model,
                    exc,
                )
                if is_key_failover_error(exc):
                    # Try next API key (rate limit / auth / quota).
                    break
                # Model-specific failure (e.g. 404) — try next model on same key.
                continue
        else:
            # All models exhausted for this key without a failover break.
            continue

    if last_error:
        logger.warning("Groq generate exhausted all keys/models: %s", last_error)
    return None
