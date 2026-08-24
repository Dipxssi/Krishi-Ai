"""Generation prefers Groq, then Gemini."""

import os

os.environ["GEMINI_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.services import llm


def test_generate_prefers_groq(monkeypatch):
    monkeypatch.setattr(llm, "_generate_groq", lambda prompt, system=None: "from groq")
    monkeypatch.setattr(llm, "_generate_gemini", lambda prompt, system=None: "from gemini")
    assert llm.generate("hello") == "from groq"


def test_generate_falls_back_to_gemini(monkeypatch):
    monkeypatch.setattr(llm, "_generate_groq", lambda prompt, system=None: None)
    monkeypatch.setattr(llm, "_generate_gemini", lambda prompt, system=None: "from gemini")
    assert llm.generate("hello") == "from gemini"


def test_generate_returns_none_when_both_fail(monkeypatch):
    monkeypatch.setattr(llm, "_generate_groq", lambda prompt, system=None: None)
    monkeypatch.setattr(llm, "_generate_gemini", lambda prompt, system=None: None)
    assert llm.generate("hello") is None


def test_is_llm_available_with_either_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    assert llm.is_llm_available() is True
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_test")
    get_settings.cache_clear()
    assert llm.is_llm_available() is True
    get_settings.cache_clear()
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    get_settings.cache_clear()
    assert llm.is_llm_available() is False
    get_settings.cache_clear()
