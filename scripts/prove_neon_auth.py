"""Prove Neon Postgres + auth signup/login/me end-to-end."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import get_engine, init_db, normalize_database_url  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    if not url.startswith("postgresql"):
        raise SystemExit(f"Expected postgres DATABASE_URL, got scheme {url.split('://', 1)[0]}")
    print(f"driver_ok {url.split('://', 1)[0]}")

    init_db()
    with get_engine().connect() as conn:
        one = conn.execute(text("select 1")).scalar()
        print(f"select {one}")
        tables = conn.execute(
            text("select tablename from pg_tables where schemaname='public' order by 1")
        ).fetchall()
        print("tables", [t[0] for t in tables])

    email = f"farmer-{uuid.uuid4().hex[:10]}@example.com"
    password = "testpass123"
    client = TestClient(app)

    signup = client.post(
        "/auth/signup",
        json={"name": "Neon Farmer", "email": email, "password": password, "location": "Punjab"},
    )
    print("signup_status", signup.status_code)
    signup.raise_for_status()
    body = signup.json()
    assert body["access_token"]
    assert body["user"]["email"] == email
    farmer_id = body["user"]["farmer_id"]
    print("signup_ok farmer_id_prefix", farmer_id[:8])

    login = client.post("/auth/login", json={"email": email, "password": password})
    print("login_status", login.status_code)
    login.raise_for_status()
    token = login.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    print("me_status", me.status_code)
    me.raise_for_status()
    assert me.json()["farmer_id"] == farmer_id
    print("auth_e2e_ok")


if __name__ == "__main__":
    main()
