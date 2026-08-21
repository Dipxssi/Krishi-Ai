"""BM25 + optional Gemini dense hybrid retrieval over local crop knowledge."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.services import llm

_corpus: list[dict[str, Any]] = []
_tokenized: list[list[str]] = []
_bm25: BM25Okapi | None = None
_dense_vectors: list[list[float]] | None = None


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
            # Split on ## headings
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
    global _corpus, _tokenized, _bm25, _dense_vectors
    if _bm25 is not None:
        return
    _corpus = _load_documents()
    _tokenized = [_tokenize(f"{d.get('title','')} {d.get('text','')}") for d in _corpus]
    _bm25 = BM25Okapi(_tokenized) if _tokenized else None
    _dense_vectors = None


def rebuild_index() -> None:
    global _bm25, _dense_vectors
    _bm25 = None
    _dense_vectors = None
    ensure_index()


def _ensure_dense() -> list[list[float]] | None:
    global _dense_vectors
    ensure_index()
    if _dense_vectors is not None:
        return _dense_vectors
    if not _corpus:
        return None
    texts = [f"{d.get('title','')}. {d.get('text','')}" for d in _corpus]
    vectors = llm.embed(texts)
    if vectors and len(vectors) == len(texts):
        _dense_vectors = vectors
    return _dense_vectors


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def search_knowledge(query: str, crop: str | None = None, top_k: int = 3) -> list[dict[str, Any]]:
    ensure_index()
    if not _corpus or _bm25 is None:
        return []

    indices = list(range(len(_corpus)))
    if crop:
        crop_l = crop.lower()
        filtered = [i for i in indices if (_corpus[i].get("crop") or "").lower() in ("", crop_l) or crop_l in (_corpus[i].get("text") or "").lower()]
        if filtered:
            indices = filtered

    tokens = _tokenize(query)
    bm25_scores = _bm25.get_scores(tokens)

    dense_scores = [0.0] * len(_corpus)
    dense = _ensure_dense()
    q_vecs = llm.embed([query]) if dense else None
    if dense and q_vecs:
        qv = q_vecs[0]
        for i in indices:
            dense_scores[i] = _cosine(qv, dense[i])

    # Hybrid: normalize BM25 then blend
    subset_bm25 = [bm25_scores[i] for i in indices]
    mx = max(subset_bm25) if subset_bm25 else 0.0
    ranked: list[tuple[float, int]] = []
    for i in indices:
        bm = (bm25_scores[i] / mx) if mx > 0 else 0.0
        ds = dense_scores[i]
        score = 0.6 * bm + 0.4 * ds if dense else bm
        ranked.append((score, i))
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
