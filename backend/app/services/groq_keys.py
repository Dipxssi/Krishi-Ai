"""Groq API key pool — supports GROQ_API_KEY + comma-separated GROQ_API_KEYS failover."""

from __future__ import annotations

import logging
import threading
from typing import Iterable

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_rr_index = 0


def _split_keys(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    parts: list[str] = []
    for chunk in str(raw).replace("\n", ",").split(","):
        key = chunk.strip().strip('"').strip("'")
        if key:
            parts.append(key)
    return parts


def list_groq_api_keys() -> list[str]:
    """Unique keys preserving order: GROQ_API_KEYS first, then GROQ_API_KEY."""
    settings = get_settings()
    ordered: list[str] = []
    seen: set[str] = set()
    for key in _split_keys(getattr(settings, "groq_api_keys", None)) + _split_keys(
        settings.groq_api_key
    ):
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered


def has_groq_api_key() -> bool:
    return bool(list_groq_api_keys())


def next_groq_api_key() -> str | None:
    """Round-robin pick for load spreading across free-tier quotas."""
    global _rr_index
    keys = list_groq_api_keys()
    if not keys:
        return None
    with _lock:
        key = keys[_rr_index % len(keys)]
        _rr_index = (_rr_index + 1) % len(keys)
        return key


def is_key_failover_error(exc: BaseException) -> bool:
    """True when another Groq key may succeed (rate limit / auth / quota)."""
    status = getattr(exc, "status_code", None)
    response = getattr(exc, "response", None)
    if status is None and response is not None:
        status = getattr(response, "status_code", None)
    if status in (401, 403, 429, 503):
        return True
    msg = str(exc).lower()
    needles = (
        "429",
        "401",
        "403",
        "rate limit",
        "ratelimit",
        "quota",
        "too many requests",
        "invalid api key",
        "unauthorized",
        "forbidden",
        "over capacity",
        "capacity",
    )
    return any(n in msg for n in needles)


def iter_groq_api_keys_for_attempt() -> Iterable[str]:
    """Start at round-robin cursor, then try remaining keys once each."""
    keys = list_groq_api_keys()
    if not keys:
        return []
    start = 0
    with _lock:
        global _rr_index
        start = _rr_index % len(keys)
        _rr_index = (_rr_index + 1) % len(keys)
    return [keys[(start + i) % len(keys)] for i in range(len(keys))]


def reset_groq_key_cursor() -> None:
    """Test helper."""
    global _rr_index
    with _lock:
        _rr_index = 0
