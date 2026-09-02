"""Generation uses Groq only."""

import os

os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.services import llm


def test_generate_uses_groq(monkeypatch):
    class FakeMessage:
        content = "from groq"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        @staticmethod
        def create(**_kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(llm, "_get_groq_client", lambda: FakeClient())
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    get_settings.cache_clear()
    assert llm.generate("hello") == "from groq"
    get_settings.cache_clear()


def test_generate_returns_none_when_groq_fails(monkeypatch):
    monkeypatch.setattr(llm, "_get_groq_client", lambda: None)
    assert llm.generate("hello") is None


def test_is_llm_available_requires_groq_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    get_settings.cache_clear()
    assert llm.is_llm_available() is True
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    assert llm.is_llm_available() is False
    get_settings.cache_clear()
