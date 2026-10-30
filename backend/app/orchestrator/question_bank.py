"""Retrieval bank of likely farmer questions.

Index rows live in backend/data/question_bank/{agent}.{lang}.jsonl.
Holdout rows stay in those files and are not loaded for matching.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.schemas.models import EvidenceItem
from app.services.multilingual import _current_farmer_question, detect_language

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_INDEX: dict[str, "_LangIndex"] | None = None
_LOANS: dict[str, dict] | None = None
_WARNED_MISSING = False

UNKNOWN_NEXT_STEP = {
    "en": (
        "This exact detail is not in the curated records. "
        "Visit the nearest Krishi Vigyan Kendra (KVK) with your land records and crop plan."
    ),
    "hi": (
        "यह विवरण उपलब्ध अभिलेखों में नहीं है। "
        "अपने जमीन के कागजात और फसल योजना के साथ निकटतम कृषि विज्ञान केंद्र (KVK) जाएं।"
    ),
    "kn": (
        "ಈ ವಿವರ ಲಭ್ಯ ದಾಖಲೆಗಳಲ್ಲಿ ಇಲ್ಲ. "
        "ನಿಮ್ಮ ಭೂ ದಾಖಲೆ ಮತ್ತು ಬೆಳೆ ಯೋಜನೆಯೊಂದಿಗೆ ಹತ್ತಿರದ ಕೃಷಿ ವಿಜ್ಞಾನ ಕೇಂದ್ರ (KVK) ಗೆ ಹೋಗಿ."
    ),
}


@dataclass(frozen=True)
class BankRow:
    id: str
    agent: str
    language: str
    intent: str
    crop: str | None
    place: str | None
    question: str
    linked_record_id: str | None
    next_step: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class BankHit:
    score: float
    row: BankRow


class _LangIndex:
    def __init__(self) -> None:
        self.rows: list[BankRow] = []
        self.by_token: dict[str, list[int]] = {}

    def add(self, row: BankRow) -> None:
        idx = len(self.rows)
        self.rows.append(row)
        for token in row.tokens:
            self.by_token.setdefault(token, []).append(idx)


def tokenize(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.lower()))


def overlap(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def bank_dir() -> Path:
    return Path(get_settings().knowledge_dir).parent / "question_bank"


def clear_cache() -> None:
    global _INDEX, _LOANS, _WARNED_MISSING
    _INDEX = None
    _LOANS = None
    _WARNED_MISSING = False


def _warn_missing(path: Path) -> None:
    global _WARNED_MISSING
    if _WARNED_MISSING:
        return
    logger.warning("Question bank is missing at %s. Routing will use the phrase matcher only.", path)
    _WARNED_MISSING = True


def _loans_by_id() -> dict[str, dict]:
    global _LOANS
    if _LOANS is not None:
        return _LOANS
    path = Path(get_settings().knowledge_dir) / "loans.json"
    _LOANS = {}
    if not path.exists():
        return _LOANS
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read loan catalog at %s", path)
        return _LOANS
    if isinstance(payload, list):
        _LOANS = {item["id"]: item for item in payload if isinstance(item, dict) and item.get("id")}
    return _LOANS


def _load() -> dict[str, _LangIndex]:
    global _INDEX
    if _INDEX is not None:
        return _INDEX
    indexes: dict[str, _LangIndex] = {}
    root = bank_dir()
    if not root.is_dir():
        _warn_missing(root)
        _INDEX = indexes
        return _INDEX
    files = sorted(root.glob("*.jsonl"))
    if not files:
        _warn_missing(root)
    for path in files:
        lang = path.stem.split(".")[-1]
        bucket = indexes.setdefault(lang, _LangIndex())
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.warning("Could not read question bank file %s", path)
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping a bad question-bank line in %s", path)
                continue
            if raw.get("split") != "index":
                continue
            question = str(raw.get("question") or "")
            row = BankRow(
                id=str(raw.get("id") or ""),
                agent=str(raw.get("agent") or ""),
                language=str(raw.get("language") or lang),
                intent=str(raw.get("intent") or ""),
                crop=raw.get("crop"),
                place=raw.get("place"),
                question=question,
                linked_record_id=raw.get("linked_record_id"),
                next_step=str(raw.get("next_step") or ""),
                tokens=tokenize(question),
            )
            if row.agent and row.tokens:
                bucket.add(row)
    _INDEX = indexes
    return _INDEX


def neighbors(question: str, language: str, k: int = 5) -> list[BankHit]:
    """Return the closest index rows in one language. A missing bank returns []."""
    try:
        indexes = _load()
    except Exception:
        logger.exception("Question bank failed to load")
        return []
    bucket = indexes.get(language)
    if bucket is None or not bucket.rows:
        return []
    query_tokens = tokenize(question)
    if not query_tokens:
        return []
    candidate_ids: set[int] = set()
    for token in query_tokens:
        candidate_ids.update(bucket.by_token.get(token, ()))
    scored: list[BankHit] = []
    for idx in candidate_ids:
        row = bucket.rows[idx]
        score = overlap(query_tokens, row.tokens)
        if score > 0:
            scored.append(BankHit(score=score, row=row))
    scored.sort(key=lambda hit: (-hit.score, hit.row.id))
    return scored[:k]


def matching_agent(question: str, language: str) -> str | None:
    """Agent agreed by the top neighbors, or None when the match is weak."""
    try:
        hits = neighbors(question, language, k=5)
    except Exception:
        logger.exception("Question bank lookup failed")
        return None
    if not hits or hits[0].score < 0.55:
        return None
    counts = Counter(hit.row.agent for hit in hits)
    agent, votes = counts.most_common(1)[0]
    if votes >= 3:
        return agent
    return None


def best_for_agent(agent: str, question: str, language: str) -> BankHit | None:
    try:
        indexes = _load()
    except Exception:
        logger.exception("Question bank failed to load")
        return None
    bucket = indexes.get(language)
    if bucket is None:
        return None
    query_tokens = tokenize(question)
    if not query_tokens:
        return None
    best: BankHit | None = None
    seen: set[int] = set()
    for token in query_tokens:
        for idx in bucket.by_token.get(token, ()):
            if idx in seen:
                continue
            seen.add(idx)
            row = bucket.rows[idx]
            if row.agent != agent:
                continue
            score = overlap(query_tokens, row.tokens)
            if best is None or score > best.score or (score == best.score and row.id < best.row.id):
                best = BankHit(score=score, row=row)
    return best


def catalog_appendix(record_id: str | None) -> str:
    if not record_id:
        return ""
    loan = _loans_by_id().get(record_id)
    if not loan:
        return ""
    rate = loan.get("interest_rate_percent")
    effective = loan.get("effective_rate_with_subvention_percent")
    parts = [f"Catalog record {loan.get('name')}."]
    if rate is not None:
        parts.append(f"Interest {rate} percent.")
    if effective is not None:
        parts.append(f"With interest subvention about {effective} percent.")
    if loan.get("max_amount_inr") is not None:
        parts.append(f"Limit {loan.get('max_amount_inr')} rupees.")
    if loan.get("eligibility"):
        parts.append(f"Eligibility: {loan.get('eligibility')}.")
    if loan.get("where_to_apply"):
        parts.append(f"Where to apply: {loan.get('where_to_apply')}.")
    return " ".join(parts)


def guidance_text(agent: str, query: str, *, tools_empty: bool, always_if_strong: bool = False) -> tuple[str | None, str | None]:
    """Return (text, evidence source) for a bank next step, or (None, None)."""
    question = _current_farmer_question(query)
    language = detect_language(question, fallback="en")
    if language not in UNKNOWN_NEXT_STEP:
        language = "en"
    hit = best_for_agent(agent, question, language)
    if hit is not None and hit.score >= 0.55 and (tools_empty or always_if_strong):
        text = hit.row.next_step
        extra = catalog_appendix(hit.row.linked_record_id)
        if extra:
            text = f"{text} {extra}"
        return text, f"question_bank:{hit.row.id}"
    if tools_empty:
        return UNKNOWN_NEXT_STEP[language], "question_bank:unknown"
    return None, None


def apply_guidance(
    agent: str,
    query: str,
    draft: str,
    evidence: list[EvidenceItem],
    *,
    tools_empty: bool,
    always_if_strong: bool = False,
) -> str:
    text, source = guidance_text(
        agent,
        query,
        tools_empty=tools_empty,
        always_if_strong=always_if_strong,
    )
    if not text or not source:
        return draft
    evidence.append(EvidenceItem(source=source, value=text, unit="next_step", agent=agent))
    return f"{draft}\n{text}"
