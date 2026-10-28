"""API endpoints for verified agricultural help and nearby KVK centers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.services.nearby_help import find_nearby_agricultural_help

router = APIRouter(prefix="/help", tags=["help"])


@router.get("/nearby")
def nearby_agricultural_help(
    query: str | None = Query(default=None, description="Village, District, or State text search"),
    district: str | None = Query(default=None, description="District name"),
    pincode: str | None = Query(default=None, description="6-digit postal PIN code"),
    lat: float | None = Query(default=None, description="Farmer device latitude (with permission)"),
    lon: float | None = Query(default=None, description="Farmer device longitude (with permission)"),
    limit: int = Query(default=5, ge=1, le=20),
) -> dict[str, Any]:
    """Retrieve verified official ICAR Krishi Vigyan Kendras (KVKs) and extension offices."""
    return find_nearby_agricultural_help(
        query=query,
        district=district,
        pincode=pincode,
        lat=lat,
        lon=lon,
        limit=limit,
    )
