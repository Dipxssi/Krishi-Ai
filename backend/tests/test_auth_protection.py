"""Auth gate + farmer_id binding for deployable API surface."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ROUTER_MODE"] = "keyword"
os.environ["ROUTER_THRESHOLD"] = "0.40"
os.environ["GROQ_API_KEY"] = ""
os.environ["JWT_SECRET"] = "test-jwt-secret-for-auth-protection-32b"
os.environ["APP_ENV"] = "development"

from app.core.config import get_settings
from app.db.session import init_db, reset_engine
from app.main import app


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


def _signup(client: TestClient, email: str = "farmer@example.com") -> dict:
    res = client.post(
        "/auth/signup",
        json={
            "name": "Test Farmer",
            "email": email,
            "password": "secret12",
            "location": "Nashik",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_query_requires_auth(client: TestClient):
    res = client.post("/query", json={"farmer_id": "x", "query": "hello"})
    assert res.status_code == 401


def test_farmers_get_requires_auth(client: TestClient):
    res = client.get("/farmers/someone")
    assert res.status_code == 401


def test_query_rejects_farmer_id_mismatch(client: TestClient):
    auth = _signup(client)
    token = auth["access_token"]
    res = client.post(
        "/query",
        headers=_auth_headers(token),
        json={"farmer_id": "not-my-farmer", "query": "rain this week?"},
    )
    assert res.status_code == 403


def test_query_ok_with_matching_farmer(client: TestClient):
    auth = _signup(client)
    token = auth["access_token"]
    farmer_id = auth["user"]["farmer_id"]
    res = client.post(
        "/query",
        headers=_auth_headers(token),
        json={"farmer_id": farmer_id, "query": "What is tomato market price?"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["farmer_id"] == farmer_id
    assert body["final_recommendation"]


def test_signup_login_uses_cost_10_and_creates_farm(client: TestClient):
    """Signup must stay one round trip: account, farm row, and a login that verifies."""
    auth = _signup(client, email="fast-signup@example.com")
    token = auth["access_token"]
    farmer_id = auth["user"]["farmer_id"]

    from app.db.users import get_user_by_email

    user = get_user_by_email("fast-signup@example.com")
    assert user is not None
    assert user.password_hash.startswith("$2b$10$") or user.password_hash.startswith("$2a$10$")

    farm = client.get(f"/farmers/{farmer_id}", headers=_auth_headers(token))
    assert farm.status_code == 200, farm.text
    assert farm.json()["farmer_id"] == farmer_id

    logged_in = client.post(
        "/auth/login",
        json={"email": "fast-signup@example.com", "password": "secret12"},
    )
    assert logged_in.status_code == 200, logged_in.text
    assert logged_in.json()["user"]["farmer_id"] == farmer_id

    duplicate = client.post(
        "/auth/signup",
        json={
            "name": "Test Farmer",
            "email": "fast-signup@example.com",
            "password": "secret12",
        },
    )
    assert duplicate.status_code == 409


def test_farmer_put_bound_to_token(client: TestClient):
    auth = _signup(client)
    token = auth["access_token"]
    farmer_id = auth["user"]["farmer_id"]

    denied = client.put(
        "/farmers/other-id",
        headers=_auth_headers(token),
        json={"location": "Pune", "farm_area_acres": 2.0},
    )
    assert denied.status_code == 403

    ok = client.put(
        f"/farmers/{farmer_id}",
        headers=_auth_headers(token),
        json={"location": "Pune", "farm_area_acres": 2.5, "crop": "tomato"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["location"] == "Pune"
    assert ok.json()["crop"] == "tomato"


def test_crop_diagnosis_requires_auth(client: TestClient):
    res = client.post("/crop/image-diagnosis", json={"image_base64": "aaa"})
    assert res.status_code == 401


def test_feedback_requires_auth(client: TestClient):
    res = client.post("/feedback", json={"request_id": "r1", "rating": 5})
    assert res.status_code == 401


def test_knowledge_and_help_remain_public(client: TestClient):
    assert client.get("/knowledge/summary").status_code == 200
    assert client.get("/help/nearby").status_code == 200
