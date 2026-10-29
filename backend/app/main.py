import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Vision services import `ml.*` from the monorepo root (sibling of backend/).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.farmers import router as farmers_router
from app.api.help import router as help_router
from app.api.knowledge import router as knowledge_router
from app.api.query import router as query_router
from app.api.route import router as route_router
from app.api.vision import router as vision_router
from app.api.voice import router as voice_router
from app.core.config import get_settings
from app.db.conversations import ConversationRow  # noqa: F401 — register tables
from app.db.session import init_db
from app.db.users import UserRow  # noqa: F401 — register tables
from app.services.audit import FeedbackRow, QueryRunRow  # noqa: F401 — register tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.ensure_secure_for_production()
    init_db()
    yield


app = FastAPI(
    title="KrishiAi Farmer Decision Support",
    version="1.0.0",
    lifespan=lifespan,
)

_settings = get_settings()
_cors_kwargs: dict = {
    "allow_origins": _settings.cors_origin_list(),
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
_cors_regex = _settings.cors_origin_regex()
if _cors_regex:
    _cors_kwargs["allow_origin_regex"] = _cors_regex
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(query_router)
app.include_router(route_router)
app.include_router(farmers_router)
app.include_router(knowledge_router)
app.include_router(help_router)
app.include_router(vision_router)
app.include_router(audit_router)
app.include_router(voice_router)


@app.get("/")
def root():
    return {
        "message": "KrishiAi V1 backend is running",
        "docs": "/docs",
        "endpoints": [
            "/health",
            "/auth/signup",
            "/auth/login",
            "/auth/me",
            "/conversations",
            "/query",
            "/route",
            "/farmers",
            "/knowledge",
            "/crop/image-diagnosis",
            "/crop/elasticnet-diagnosis",
            "/audit",
            "/voice",
        ],
    }


@app.get("/health")
def health():
    """Lightweight probe for offline clients and field-relay status scripts."""
    return {"status": "ok", "service": "krishiai"}
