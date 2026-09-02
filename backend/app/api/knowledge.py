"""Browse curated knowledge corpus for the frontend hub."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from app.core.config import get_settings

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _load_json(name: str) -> list[dict[str, Any]]:
    path = Path(get_settings().knowledge_dir) / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/summary")
def knowledge_summary() -> dict[str, Any]:
    schemes = _load_json("schemes.json")
    crops = _load_json("crops.json")
    loans = _load_json("loans.json")
    categories = sorted({s.get("category", "other") for s in schemes})
    crop_names = sorted({c.get("crop") for c in crops if c.get("crop")})
    return {
        "scheme_count": len(schemes),
        "crop_article_count": len(crops),
        "loan_count": len(loans),
        "scheme_categories": categories,
        "crops_covered": crop_names,
    }


@router.get("/schemes")
def list_schemes(
    category: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    items = _load_json("schemes.json")
    if category:
        cat = category.lower()
        items = [s for s in items if str(s.get("category", "")).lower() == cat]
    if q:
        needle = q.lower()
        items = [
            s
            for s in items
            if needle in str(s.get("name", "")).lower()
            or needle in str(s.get("benefit", "")).lower()
            or any(needle in str(k).lower() for k in s.get("keywords", []))
        ]
    return {"items": items[:limit], "total": len(items)}


@router.get("/crops")
def list_crop_articles(
    crop: str | None = None,
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    items = _load_json("crops.json")
    if crop == "__general__":
        items = [c for c in items if c.get("crop") is None]
    elif crop:
        ck = crop.lower()
        items = [c for c in items if str(c.get("crop", "")).lower() == ck]
    if q:
        needle = q.lower()
        items = [
            c
            for c in items
            if needle in str(c.get("title", "")).lower() or needle in str(c.get("text", "")).lower()
        ]
    return {"items": items[:limit], "total": len(items)}


@router.get("/loans")
def list_loans(
    category: str | None = None,
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    items = _load_json("loans.json")
    if category:
        cat = category.lower()
        items = [l for l in items if str(l.get("category", "")).lower() == cat]
    return {"items": items[:limit], "total": len(items)}
