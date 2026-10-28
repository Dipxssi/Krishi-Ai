"""Shared helpers so API tests can call JWT-protected routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.users import UserRow
from app.services.auth_service import get_current_user


def signup_and_headers(
    client: TestClient,
    *,
    email: str = "test-farmer@example.com",
    name: str = "Test Farmer",
    location: str = "Nashik",
    password: str = "secret12",
) -> tuple[dict[str, str], str, dict]:
    """Return (Authorization headers, farmer_id, auth response body)."""
    res = client.post(
        "/auth/signup",
        json={
            "name": name,
            "email": email,
            "password": password,
            "location": location,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    farmer_id = body["user"]["farmer_id"]
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    return headers, farmer_id, body


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def install_auth_override(app: FastAPI, *, farmer_id: str = "test-farmer") -> UserRow:
    """Bypass JWT for endpoint unit tests that are not about auth."""
    user = UserRow(
        id="test-user-id",
        email="override@example.com",
        name="Override User",
        password_hash="unused",
        farmer_id=farmer_id,
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return user


def clear_auth_override(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_current_user, None)
