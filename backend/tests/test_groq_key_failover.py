"""Groq multi-key pool and LLM failover."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import get_settings
from app.services import groq_keys, llm


@pytest.fixture(autouse=True)
def clear_settings_and_cursor():
    get_settings.cache_clear()
    groq_keys.reset_groq_key_cursor()
    yield
    get_settings.cache_clear()
    groq_keys.reset_groq_key_cursor()


def test_list_keys_merges_primary_and_pool(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "primary-key")
    monkeypatch.setenv("GROQ_API_KEYS", "extra-a, extra-b, primary-key")
    get_settings.cache_clear()
    assert groq_keys.list_groq_api_keys() == ["extra-a", "extra-b", "primary-key"]


def test_generate_fails_over_on_rate_limit(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GROQ_API_KEYS", "bad-key,good-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")
    get_settings.cache_clear()
    groq_keys.reset_groq_key_cursor()

    class RateLimitError(Exception):
        status_code = 429

    good_response = MagicMock()
    good_response.choices = [MagicMock(message=MagicMock(content="ok advice"), finish_reason="stop")]

    clients: list[MagicMock] = []

    def fake_groq(*, api_key: str, timeout: float, max_retries: int):
        client = MagicMock()
        clients.append((api_key, client))
        if api_key == "bad-key":
            client.chat.completions.create.side_effect = RateLimitError("429 rate limit")
        else:
            client.chat.completions.create.return_value = good_response
        return client

    with patch("groq.Groq", side_effect=fake_groq):
        text = llm.generate("hello", system="sys")

    assert text == "ok advice"
    assert [k for k, _ in clients] == ["bad-key", "good-key"]


def test_is_key_failover_error_detects_429():
    class E(Exception):
        status_code = 429

    assert groq_keys.is_key_failover_error(E("nope"))
    assert groq_keys.is_key_failover_error(RuntimeError("Rate limit exceeded"))
    assert not groq_keys.is_key_failover_error(RuntimeError("model not found"))
