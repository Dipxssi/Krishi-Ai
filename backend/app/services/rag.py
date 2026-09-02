"""BM25 retrieval over local crop knowledge."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings

_corpus: list[dict[str, Any]] = []
_tokenized: list[list[str]] = []
_bm25: BM25Okapi | None = None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _load_documents() -> list[dict[str, Any]]:
    settings = get_settings()
    knowledge_dir = Path(settings.knowledge_dir)
    docs: list[dict[str, Any]] = []
    if not knowledge_dir.exists():
        return docs
    for path in sorted(knowledge_dir.glob("**/*")):
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for i, item in enumerate(data):
                    docs.append(
                        {
                            "id": item.get("id", f"{path.stem}-{i}"),
                            "crop": item.get("crop"),
                            "title": item.get("title", path.stem),
                            "text": item.get("text", ""),
                            "source": str(path.name),
                        }
                    )
            elif isinstance(data, dict):
                docs.append(
                    {
                        "id": data.get("id", path.stem),
                        "crop": data.get("crop"),
                        "title": data.get("title", path.stem),
                        "text": data.get("text", ""),
                        "source": str(path.name),
                    }
                )
        elif path.suffix.lower() == ".md":
            text = path.read_text(encoding="utf-8")
            chunks = re.split(r"\n##\s+", text)
            for i, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if not chunk:
                    continue
                title = chunk.split("\n", 1)[0].strip("# ").strip()
                docs.append(
                    {
                        "id": f"{path.stem}-{i}",
                        "crop": None,
                        "title": title,
                        "text": chunk,
                        "source": path.name,
                    }
                )
    return docs


def ensure_index() -> None:
    global _corpus, _tokenized, _bm25
    if _bm25 is not None:
        return
    _corpus = _load_documents()
    _tokenized = [_tokenize(f"{d.get('title','')} {d.get('text','')}") for d in _corpus]
    _bm25 = BM25Okapi(_tokenized) if _tokenized else None


def rebuild_index() -> None:
    global _bm25
    _bm25 = None
    ensure_index()


def search_knowledge(query: str, crop: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    ensure_index()
    if not _corpus or _bm25 is None:
        return []

    indices = list(range(len(_corpus)))
    if crop:
        crop_l = crop.lower()
        filtered = [
            i
            for i in indices
            if (_corpus[i].get("crop") or "").lower() in ("", crop_l)
            or crop_l in (_corpus[i].get("text") or "").lower()
        ]
        if filtered:
            indices = filtered

    tokens = _tokenize(query)
    bm25_scores = _bm25.get_scores(tokens)

    subset_bm25 = [bm25_scores[i] for i in indices]
    mx = max(subset_bm25) if subset_bm25 else 0.0
    ranked: list[tuple[float, int]] = []
    for i in indices:
        bm = (bm25_scores[i] / mx) if mx > 0 else 0.0
        ranked.append((bm, i))
    ranked.sort(reverse=True)

    results = []
    for score, i in ranked[:top_k]:
        doc = _corpus[i]
        results.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "text": doc["text"][:800],
                "crop": doc.get("crop"),
                "source": doc["source"],
                "score": round(float(score), 4),
            }
        )
    return results
