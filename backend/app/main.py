from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.audit import router as audit_router
from app.api.farmers import router as farmers_router
from app.api.knowledge import router as knowledge_router
from app.api.query import router as query_router
from app.api.route import router as route_router
from app.api.vision import router as vision_router
from app.api.voice import router as voice_router
from app.db.session import init_db
from app.services.audit import FeedbackRow, QueryRunRow  # noqa: F401 — register tables


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="KrishiAi Farmer Decision Support",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query_router)
app.include_router(route_router)
app.include_router(farmers_router)
app.include_router(knowledge_router)
app.include_router(vision_router)
app.include_router(audit_router)
app.include_router(voice_router)


@app.get("/")
def root():
    return {
        "message": "KrishiAi V1 backend is running",
        "docs": "/docs",
        "endpoints": ["/query", "/route", "/farmers", "/knowledge", "/crop/image-diagnosis", "/audit", "/voice"],
    }
