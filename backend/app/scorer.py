from dataclasses import dataclass

MET = 0.5


@dataclass
class ScoreResult:
    score: int
    must_met: int
    must_total: int
    flagged: bool


def score(items: list[tuple[str, float, float]]) -> ScoreResult:
    """items: (type 'must'|'nice', weight, probability)."""
    if not items:
        raise ValueError("score() needs at least one requirement")
    total = sum(w for _, w, _ in items)
    weighted = sum(w * p for _, w, p in items)
    musts = [p for t, _, p in items if t == "must"]
    met = sum(p >= MET for p in musts)
    return ScoreResult(round(100 * weighted / total), met, len(musts), met < len(musts))
