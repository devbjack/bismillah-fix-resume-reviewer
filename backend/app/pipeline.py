from __future__ import annotations

from dataclasses import dataclass

from app.chunker import chunk_text
from app.decider import Decider
from app.retriever import Embed, ResumeIndex
from app.scorer import ScoreResult, score


class NoTextError(Exception):
    pass


@dataclass
class ReqResult:
    requirement_id: int
    probability: float
    evidence: str


def review(text: str, requirements: list[dict], decider: Decider,
           embed: Embed) -> tuple[ScoreResult, list[ReqResult]]:
    """requirements: dicts with id, text, type, weight."""
    chunks = chunk_text(text)
    if not chunks:
        raise NoTextError()
    index = ResumeIndex(chunks, embed)
    results = []
    for req in requirements:
        top = index.top(req["text"])
        results.append(ReqResult(req["id"], decider.p_met(req["text"], top), top[0]))
    sr = score([(req["type"], req["weight"], r.probability) for req, r in zip(requirements, results)])
    return sr, results
