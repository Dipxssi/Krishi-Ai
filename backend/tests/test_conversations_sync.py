"""Cross-device conversation sync API."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["ROUTER_THRESHOLD"] = "0.40"
os.environ["GROQ_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-jwt-secret-for-conversation-sync-32b"
os.environ["APP_ENV"] = "development"

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app
from tests.auth_helpers import signup_and_headers


@pytest.fixture(autouse=True)
def _reset_db():
    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()


@pytest.fixture
def client():
    return TestClient(app)


def test_conversations_require_auth(client: TestClient):
    res = client.get("/conversations")
    assert res.status_code == 401


def test_put_get_delete_conversation_roundtrip(client: TestClient):
    headers, _farmer_id, _ = signup_and_headers(client, email="sync-a@example.com")

    payload = {
        "conversations": [
            {
                "id": "c-wheat-1",
                "title": "Yellow leaves",
                "updatedAt": 1_700_000_000_000,
                "messages": [
                    {"id": "m1", "role": "user", "content": "My wheat leaves are yellow"},
                    {
                        "id": "m2",
                        "role": "assistant",
                        "content": "Check nitrogen and drainage.",
                    },
                ],
            }
        ]
    }
    put = client.put("/conversations", json=payload, headers=headers)
    assert put.status_code == 200, put.text
    assert len(put.json()["conversations"]) == 1

    got = client.get("/conversations", headers=headers)
    assert got.status_code == 200
    items = got.json()["conversations"]
    assert len(items) == 1
    assert items[0]["id"] == "c-wheat-1"
    assert items[0]["messages"][0]["content"].startswith("My wheat")

    deleted = client.delete("/conversations/c-wheat-1", headers=headers)
    assert deleted.status_code == 204
    empty = client.get("/conversations", headers=headers)
    assert empty.json()["conversations"] == []


def test_older_update_does_not_clobber_newer(client: TestClient):
    headers, _, _ = signup_and_headers(client, email="sync-b@example.com")
    client.put(
        "/conversations",
        json={
            "conversations": [
                {
                    "id": "c1",
                    "title": "New",
                    "updatedAt": 200,
                    "messages": [{"id": "m", "role": "user", "content": "new"}],
                }
            ]
        },
        headers=headers,
    )
    client.put(
        "/conversations",
        json={
            "conversations": [
                {
                    "id": "c1",
                    "title": "Old",
                    "updatedAt": 100,
                    "messages": [{"id": "m", "role": "user", "content": "old"}],
                }
            ]
        },
        headers=headers,
    )
    items = client.get("/conversations", headers=headers).json()["conversations"]
    assert items[0]["title"] == "New"
    assert items[0]["messages"][0]["content"] == "new"


def test_conversations_isolated_per_farmer(client: TestClient):
    headers_a, _, _ = signup_and_headers(client, email="sync-c@example.com")
    headers_b, _, _ = signup_and_headers(client, email="sync-d@example.com")
    client.put(
        "/conversations",
        json={
            "conversations": [
                {
                    "id": "only-a",
                    "title": "A chat",
                    "updatedAt": 1,
                    "messages": [{"id": "m", "role": "user", "content": "hi"}],
                }
            ]
        },
        headers=headers_a,
    )
    assert client.get("/conversations", headers=headers_b).json()["conversations"] == []
    assert len(client.get("/conversations", headers=headers_a).json()["conversations"]) == 1
