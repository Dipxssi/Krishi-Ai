"""Service for searching verified agricultural help and ICAR Krishi Vigyan Kendras (KVKs).

Strict safety policy:
- Never fabricate an office, phone number, address, or distance.
- Uses official ICAR and government institutional records only.
- Calculates true geodesic distance when coordinates are provided with permission.
- Falls back to official National Kisan Call Centre (1800-180-1551) when no exact local match exists.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from app.core.config import get_settings

OFFICIAL_KISAN_HELPLINE = "1800-180-1551"
OFFICIAL_KVK_PORTAL = "https://kvk.icar.gov.in"

_PLACE_ALIASES = {
    "bangalore": "bengaluru",
    "bengalore": "bengaluru",
    "belgaum": "belagavi",
    "belgam": "belagavi",
    "mysore": "mysuru",
    "mangalore": "dakshina kannada",
    "hubli": "dharwad",
    "hubballi": "dharwad",
}

_KVK_ADVICE_RE = re.compile(
    r"\bKVK\b|Krishi Vigyan|extension officer|कृषि विज्ञान|ಕೃಷಿ ವಿಜ್ಞಾನ",
    re.IGNORECASE,
)


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(radius_km * c, 1)


def load_kvk_directory() -> list[dict[str, Any]]:
    path = Path(get_settings().knowledge_dir) / "official_kvk_directory.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _normalize_place(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    for source, target in _PLACE_ALIASES.items():
        lowered = re.sub(rf"\b{source}\b", target, lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def maps_url(latitude: float, longitude: float) -> str:
    """Open the office pin in Google Maps. Coordinates come from the ICAR directory."""
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def nearest_verified_kvk(location: str | None) -> dict[str, Any] | None:
    """Pick the verified KVK for a farm place. Never invents an office.

    A bare city name such as Bengaluru prefers the Urban kendra. 'Rural' in the
    place name keeps the rural kendra.
    """
    raw = (location or "").strip()
    if not raw or raw.lower() in {"india", "unknown"}:
        return None
    place = _normalize_place(raw)
    if not place:
        return None
    wants_rural = "rural" in place
    pin_match = re.search(r"\b(\d{6})\b", raw)
    pin = pin_match.group(1) if pin_match else ""
    scored: list[tuple[int, dict[str, Any]]] = []
    for center in load_kvk_directory():
        district = _normalize_place(str(center.get("district") or ""))
        state = _normalize_place(str(center.get("state") or ""))
        center_pin = str(center.get("pincode") or "")
        score = 0
        if pin and pin == center_pin:
            score += 8
        district_tokens = [
            token
            for token in district.split()
            if len(token) > 3 and token not in {"rural", "urban"}
        ]
        if district and district in place:
            score += 6
        elif district_tokens and all(token in place for token in district_tokens):
            score += 5
        elif district_tokens and any(token in place for token in district_tokens):
            score += 3
        if state and state in place:
            score += 1
        if score <= 0:
            continue
        if "urban" in district and not wants_rural:
            score += 2
        if "rural" in district and wants_rural:
            score += 2
        if "rural" in district and not wants_rural:
            score -= 1
        scored.append((score, center))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    chosen = dict(scored[0][1])
    chosen["verified"] = True
    return chosen


def format_nearby_kvk_block(location: str | None, language: str = "en") -> str:
    """Short office card: name, address, phone, and a map pin. Empty when unknown."""
    center = nearest_verified_kvk(location)
    if not center:
        return ""
    name = str(center.get("name") or "").strip()
    address = str(center.get("address") or "").strip()
    phone = str(center.get("phone") or "").strip()
    lat = center.get("latitude")
    lon = center.get("longitude")
    map_line = ""
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        url = maps_url(float(lat), float(lon))
        if language == "hi":
            map_line = f"[लाइव लोकेशन खोलें]({url})"
        elif language == "kn":
            map_line = f"[ಲೈವ್ ಸ್ಥಳ ತೆರೆಯಿರಿ]({url})"
        else:
            map_line = f"[Open live location]({url})"
    if language == "hi":
        lines = ["**सबसे नज़दीकी कृषि विज्ञान केंद्र**", name, address]
        if phone:
            lines.append(f"फ़ोन: {phone}")
    elif language == "kn":
        lines = ["**ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ**", name, address]
        if phone:
            lines.append(f"ಫೋನ್: {phone}")
    else:
        lines = ["**Nearest verified KVK**", name, address]
        if phone:
            lines.append(f"Phone: {phone}")
    if map_line:
        lines.append(map_line)
    return "\n".join(line for line in lines if line)


def append_nearby_kvk_office(recommendation: str, location: str | None, language: str = "en") -> str:
    """Add the real nearby office when the answer tells the farmer to visit a KVK."""
    if not recommendation or not _KVK_ADVICE_RE.search(recommendation):
        return recommendation
    if "maps/search/?api=1&query=" in recommendation:
        return recommendation
    block = format_nearby_kvk_block(location, language)
    if not block:
        return recommendation
    return recommendation.rstrip() + "\n\n" + block


def find_nearby_agricultural_help(
    *,
    query: str | None = None,
    district: str | None = None,
    pincode: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Find verified nearby ICAR KVKs or government agriculture extension offices."""
    all_centers = load_kvk_directory()
    matched: list[dict[str, Any]] = []

    # 1. Geographic distance search if coordinates are supplied
    if lat is not None and lon is not None:
        try:
            user_lat = float(lat)
            user_lon = float(lon)
            with_dist = []
            for center in all_centers:
                c_lat = center.get("latitude")
                c_lon = center.get("longitude")
                if c_lat is not None and c_lon is not None:
                    dist = _haversine_distance_km(user_lat, user_lon, c_lat, c_lon)
                    item = dict(center)
                    item["distance_km"] = dist
                    item["verified"] = True
                    with_dist.append(item)
            with_dist.sort(key=lambda x: x["distance_km"])
            matched = with_dist[:limit]
        except (ValueError, TypeError):
            matched = []

    # 2. Text / District / PIN code search
    if not matched:
        tokens = []
        if district and district.strip():
            tokens.append(district.strip().lower())
        if pincode and pincode.strip():
            tokens.append(pincode.strip().lower())
        if query and query.strip():
            tokens.extend(query.strip().lower().split())

        if tokens:
            scored_centers = []
            for center in all_centers:
                search_blob = (
                    f"{center.get('name', '')} {center.get('district', '')} "
                    f"{center.get('state', '')} {center.get('pincode', '')} "
                    f"{center.get('address', '')}"
                ).lower()
                matches = sum(1 for token in tokens if token in search_blob)
                if matches > 0:
                    scored_centers.append((matches, center))
            scored_centers.sort(key=lambda x: x[0], reverse=True)
            matched = []
            for c in scored_centers[:limit]:
                it = dict(c[1])
                it["verified"] = True
                matched.append(it)

    has_results = len(matched) > 0
    fallback_info = None

    if not has_results:
        fallback_info = {
            "notice": (
                "No verified local Krishi Vigyan Kendra was found for the exact location provided. "
                "You can reach the official Government of India Kisan Call Centre (Toll-Free 1800-180-1551) "
                "for agricultural advice or look up your district center at the official ICAR portal (https://kvk.icar.gov.in)."
            ),
            "kisan_call_centre_helpline": OFFICIAL_KISAN_HELPLINE,
            "official_portal_url": OFFICIAL_KVK_PORTAL,
            "prompt_for_district": "Enter your district name or 6-digit postal PIN code to search verified centers.",
        }

    return {
        "status": "ok" if has_results else "fallback",
        "centers": matched,
        "results": matched,
        "total": len(matched),
        "total_found": len(matched),
        "has_verified_results": has_results,
        "kisan_call_centre": OFFICIAL_KISAN_HELPLINE,
        "official_portal": OFFICIAL_KVK_PORTAL,
        "fallback_info": fallback_info,
        "fallback_notice": fallback_info["notice"] if fallback_info else None,
    }
