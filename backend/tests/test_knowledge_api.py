import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GROQ_API_KEY"] = ""
os.environ["GROQ_API_KEY"] = ""

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app


@pytest.fixture(autouse=True)
def _reset():
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()


@pytest.fixture
def client():
    return TestClient(app)


def test_knowledge_summary(client):
    r = client.get("/knowledge/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["scheme_count"] >= 10
    assert body["crop_article_count"] >= 20
    assert "tomato" in body["crops_covered"]


def test_knowledge_schemes_filter(client):
    r = client.get("/knowledge/schemes", params={"q": "drip"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert any("drip" in str(s.get("benefit", "")).lower() or "drip" in s.get("keywords", []) for s in items)


def test_knowledge_crops_general(client):
    r = client.get("/knowledge/crops", params={"crop": "__general__"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(c.get("crop") is None for c in items)


def test_knowledge_loans_list(client):
    r = client.get("/knowledge/loans")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 5
    assert any("KCC" in item.get("name", "") for item in body["items"])
