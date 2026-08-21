"""Multi-label agent router with keyword, embedding, and cost-aware selection."""

from __future__ import annotations

import math
import re
from collections import Counter

from app.core.config import get_settings
from app.orchestrator.catalog import AGENT_COST, AGENT_KEYWORDS, AGENT_PROFILES, AGENTS
from app.services import llm


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


def _cosine_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def keyword_scores(query: str) -> dict[str, float]:
    q = query.lower()
    scores: dict[str, float] = {agent: 0.0 for agent in AGENTS}
    for agent, keywords in AGENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in q)
        if hits:
            scores[agent] = min(1.0, 0.45 + 0.2 * hits)
    return scores


def embedding_scores(query: str) -> dict[str, float]:
    profiles = [AGENT_PROFILES[a] for a in AGENTS]
    dense = llm.embed([query, *profiles])
    if dense and len(dense) == 1 + len(AGENTS):
        q_vec = dense[0]
        return {
            agent: max(0.0, min(1.0, (_cosine_dense(q_vec, dense[i + 1]) + 1) / 2))
            for i, agent in enumerate(AGENTS)
        }

    # Bag-of-words fallback
    q_bow = _bow_vector(_tokenize(query))
    scores: dict[str, float] = {}
    for agent in AGENTS:
        p_bow = _bow_vector(_tokenize(AGENT_PROFILES[agent] + " " + " ".join(AGENT_KEYWORDS.get(agent, []))))
        scores[agent] = _cosine(q_bow, p_bow)
    # Softmax-ish normalize to 0-1 relative scale
    mx = max(scores.values()) if scores else 0.0
    if mx > 0:
        scores = {k: v / mx for k, v in scores.items()}
    return scores


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
    # Preserve catalog order for stability
    order = {a: i for i, a in enumerate(AGENTS)}
    return sorted(selected, key=lambda a: order.get(a, 99))


def route_query(query: str) -> tuple[list[str], dict[str, float]]:
    """Return selected agents and raw (pre-penalty) scores for debugging."""
    settings = get_settings()
    kw = keyword_scores(query)
    emb = embedding_scores(query)
    base = combine_scores(kw, emb, settings.router_mode)
    adjusted = apply_cost_penalty(base, settings.router_cost_lambda)
    selected = select_agents(adjusted, settings.router_threshold)
    return selected, adjusted


# Back-compat alias used by older imports
def route_agents(query: str, agent_scores: dict[str, float] | None = None, threshold: float = 0.60):
    if agent_scores is None:
        selected, _ = route_query(query)
        return selected
    return select_agents(agent_scores, threshold)
