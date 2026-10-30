"""Named yards where a farmer can take produce for sale.

Prices still come from Agmarknet or the estimate. These names are only the places to go.
"""

from __future__ import annotations

# Longer aliases first so "bengaluru urban" matches Bengaluru, not a shorter token.
_YARDS: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("bengaluru", "bangalore"),
        [
            "Yeshwanthpur APMC",
            "K.R. Market (City Market)",
            "Madiwala market",
            "HOPCOMS",
        ],
    ),
    (
        ("mysuru", "mysore"),
        ["APMC Mysuru, Bandipalya", "Devaraja Market"],
    ),
    (("belagavi", "belgaum"), ["APMC Belagavi"]),
    (("hubballi", "hubli"), ["APMC Hubballi"]),
    (("mandya",), ["APMC Mandya"]),
    (
        ("nashik",),
        ["Pimpalgaon Baswant APMC", "Nashik APMC"],
    ),
    (
        ("pune",),
        ["Gultekdi Market Yard, Pune", "Moshi Market Yard"],
    ),
    (("nagpur",), ["Kalamna APMC, Nagpur"]),
    (("lucknow",), ["Dubagga Sabzi Mandi, Lucknow"]),
    (("ludhiana",), ["APMC Ludhiana"]),
    (("warangal",), ["Enumamula Agriculture Market, Warangal"]),
    (("guntur",), ["Guntur APMC market yard"]),
]


def sell_markets_for(location: str) -> list[str]:
    text = (location or "").lower()
    if not text.strip():
        return []
    for keys, markets in _YARDS:
        if any(key in text for key in keys):
            return list(markets)
    return []
