"""Multi-label agent router with keyword, embedding, and cost-aware selection."""

from __future__ import annotations

import math
import re
from collections import Counter

from app.core.config import get_settings
from app.orchestrator.catalog import AGENT_COST, AGENT_KEYWORDS, AGENT_PROFILES, AGENTS
from app.schemas.models import FarmContext


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bow_vector(tokens: list[str]) -> Counter:
    return Counter(tokens)


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[t] * b[t] for t in a)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _keyword_hit(keyword: str, query: str) -> bool:
    """Match phrases by substring; match single tokens on word boundaries."""
    kw = keyword.lower()
    if " " in kw or "-" in kw:
        return kw in query
    return re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", query) is not None


def keyword_scores(query: str) -> dict[str, float]:
    q = query.lower()
    scores: dict[str, float] = {agent: 0.0 for agent in AGENTS}
    for agent, keywords in AGENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if _keyword_hit(kw, q))
        if hits:
            scores[agent] = min(1.0, 0.45 + 0.2 * hits)
    return apply_cooccurrence_boosts(q, scores)


def apply_cooccurrence_boosts(query: str, scores: dict[str, float]) -> dict[str, float]:
    """Deterministic boosts for common multi-agent farmer intents."""
    out = dict(scores)
    q = query.lower()

    def bump(agent: str, amount: float = 0.55) -> None:
        out[agent] = max(out.get(agent, 0.0), amount)

    planting = any(
        p in q for p in ("plant now", "should i plant", "planting", "plant tomatoes", "plant rice")
    )
    if planting:
        bump("weather")
        bump("market")
        bump("finance")
        # soil only if fertility/soil cues present
        if any(p in q for p in ("soil", "npk", "fertilizer", "fertility")):
            bump("soil", 0.50)

    # Profit / cost math → finance; market only when price/sell context
    if any(p in q for p in ("profit", "break-even", "break even", "estimate total", "input cost")):
        bump("finance")
        if any(p in q for p in ("price", "mandi", "market", "sell", "acres")):
            bump("market")

    # Market decision (not pure price lookup)
    if any(p in q for p in ("sell early", "hold or sell", "falling", "sell or", "decide selling")):
        bump("market")
        bump("finance")
    elif any(p in q for p in ("mandi", "market price", "demand", "storage")):
        bump("market")
        # finance only if money decision words also present
        if any(p in q for p in ("budget", "profit", "cost", "afford", "loan", "worth")):
            bump("finance")

    # Crop stress / disease → crop_health (boost high enough to survive cost tier 3)
    if any(
        p in q
        for p in (
            "blight",
            "spots",
            "fungus",
            "infection",
            "disease",
            "pest",
            "treat",
            "treatment",
            "deficiency",
            "yellow",
            "protect",
            "flowers",
            "scout",
            "stems",
        )
    ):
        bump("crop_health", 0.70)

    # Fertilizer / nutrient management → soil (+ knowledge if asking what/how)
    if any(p in q for p in ("fertilizer", "fertiliser", "nutrient", "npk", "potassium", "phosphorus", "nitrogen")):
        bump("soil")
        if any(
            p in q
            for p in (
                "practice",
                "what to apply",
                "levels",
                "guidance",
                "how to",
                "reduce dose",
                "deficiency",
                "risk",
                "treatment",
                "infection",
                "blight",
                "fungus",
            )
        ):
            bump("knowledge_retriever", 0.60)

    if any(p in q for p in ("soil", "ph ", " ph", "tuber")):
        bump("soil")
        if any(p in q for p in ("suitable", "levels", "quality", "apply")):
            bump("knowledge_retriever", 0.60)

    # Irrigation under drought/crop → weather + crop/soil
    if "irrigate" in q or ("irrigation" in q and "loan" not in q and "drip" not in q):
        bump("weather")
        if any(p in q for p in ("maize", "tomato", "potato", "crop", "leaves", "deficiency")):
            bump("crop_health", 0.70)
            bump("soil", 0.55)

    # Equipment rent/buy
    if any(
        _keyword_hit(p, q)
        for p in ("tractor", "harvester", "sprayer", "rental", "tiller", "equipment", "tilling")
    ):
        bump("equipment")
        if any(_keyword_hit(p, q) for p in ("cost", "buy", "hire", "worth", "payback", "afford", "rent")):
            bump("finance")

    # Weather stress (avoid loan+drip-only)
    if "loan" not in q and any(
        p in q for p in ("rain", "drought", "flood", "monsoon", "humidity", "temperature stress")
    ):
        bump("weather")

    return out


def bow_embedding_scores(query: str) -> dict[str, float]:
    """Local bag-of-words similarity — no Gemini calls."""
    q_bow = _bow_vector(_tokenize(query))
    scores: dict[str, float] = {}
    for agent in AGENTS:
        p_bow = _bow_vector(
            _tokenize(AGENT_PROFILES[agent] + " " + " ".join(AGENT_KEYWORDS.get(agent, [])))
        )
        scores[agent] = _cosine(q_bow, p_bow)
    mx = max(scores.values()) if scores else 0.0
    if mx > 0:
        scores = {k: v / mx for k, v in scores.items()}
    return scores


def embedding_scores(query: str, *, allow_remote: bool = True) -> dict[str, float]:
    """Local bag-of-words similarity (no external embedding API)."""
    del allow_remote  # kept for eval-script compatibility
    return bow_embedding_scores(query)


def combine_scores(
    keyword: dict[str, float],
    embedding: dict[str, float],
    mode: str,
) -> dict[str, float]:
    if mode == "keyword":
        return keyword
    if mode == "embedding":
        return embedding
    # hybrid
    return {
        agent: 0.55 * keyword.get(agent, 0.0) + 0.45 * embedding.get(agent, 0.0)
        for agent in AGENTS
    }


def apply_cost_penalty(scores: dict[str, float], cost_lambda: float) -> dict[str, float]:
    return {
        agent: score - cost_lambda * AGENT_COST.get(agent, 1)
        for agent, score in scores.items()
    }


def select_agents(
    agent_scores: dict[str, float],
    threshold: float = 0.60,
) -> list[str]:
    selected = [agent for agent, score in agent_scores.items() if score >= threshold]
    if not selected:
        selected = [max(agent_scores, key=agent_scores.get)]
    order = {a: i for i, a in enumerate(AGENTS)}
    return sorted(selected, key=lambda a: order.get(a, 99))


def score_query(
    query: str,
    *,
    mode: str,
    threshold: float,
    cost_lambda: float,
    allow_remote_embeddings: bool = True,
) -> tuple[list[str], dict[str, float]]:
    """Shared scoring path for production router and eval scripts."""
    kw = keyword_scores(query)
    if mode == "keyword":
        emb: dict[str, float] = {a: 0.0 for a in AGENTS}
    else:
        emb = embedding_scores(query, allow_remote=allow_remote_embeddings)
    base = combine_scores(kw, emb, mode)
    adjusted = apply_cost_penalty(base, cost_lambda)
    selected = select_agents(adjusted, threshold)
    return selected, adjusted


def route_query(query: str, *, has_image: bool = False) -> tuple[list[str], dict[str, float]]:
    """Return selected agents and adjusted scores."""
    settings = get_settings()
    selected, scores = score_query(
        query,
        mode=settings.router_mode if settings.router_mode != "supervised" else "hybrid",
        threshold=settings.router_threshold,
        cost_lambda=settings.router_cost_lambda,
        allow_remote_embeddings=True,
    )
    if settings.router_mode == "supervised":
        from app.orchestrator.supervised_router import route_supervised

        selected, scores = route_supervised(
            query,
            threshold=settings.router_threshold,
            cost_lambda=settings.router_cost_lambda,
        )
    if has_image:
        scores = dict(scores)
        scores["crop_health"] = max(scores.get("crop_health", 0.0), 0.72)
        selected = select_agents(scores, settings.router_threshold)
        if "crop_health" not in selected:
            selected = [*selected, "crop_health"]
    return selected, scores


def infer_risk_level(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ("blight", "pest", "disease", "sell early", "loss", "flood", "drought")):
        return "high"
    if any(w in q for w in ("profit", "budget", "price", "rain", "fertilizer")):
        return "medium"
    return "low"


def route_for_debug(
    query: str,
    context: FarmContext | None = None,
    *,
    has_image: bool = False,
) -> dict:
    from app.services.validator import missing_farm_fields

    settings = get_settings()
    selected, scores = route_query(query, has_image=has_image)
    missing = missing_farm_fields(context, selected) if context else []
    return {
        "routing_mode": settings.router_mode,
        "selected_agents": selected,
        "agent_scores": {k: round(v, 4) for k, v in scores.items()},
        "missing_information": missing,
        "risk_level": infer_risk_level(query),
    }


def route_agents(query: str, agent_scores: dict[str, float] | None = None, threshold: float = 0.60):
    if agent_scores is None:
        selected, _ = route_query(query)
        return selected
    return select_agents(agent_scores, threshold)
