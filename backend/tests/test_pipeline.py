import numpy as np
import pytest

from app.pipeline import NoTextError, review


class FakeDecider:
    def p_met(self, requirement, evidence):
        word = requirement.split()[0].lower()
        return 0.9 if any(word in e.lower() for e in evidence) else 0.1


def emb(texts):
    return np.ones((len(texts), 3))


REQS = [
    {"id": 7, "text": "Python experience", "type": "must", "weight": 2},
    {"id": 9, "text": "Docker", "type": "nice", "weight": 1},
]
RESUME = "SKILLS\nPython, SQL\n\nEXPERIENCE\nBackend Engineer 2020-2024, built APIs"


def test_review_scores_and_returns_evidence():
    sr, results = review(RESUME, REQS, FakeDecider(), emb)
    assert sr.score == 63  # (2*0.9 + 1*0.1) / 3
    assert (sr.must_met, sr.must_total, sr.flagged) == (1, 1, False)
    assert "Python" in results[0].evidence
    assert results[0].probability == 0.9 and results[1].probability == 0.1


def test_review_one_result_per_requirement_in_order():
    _, results = review(RESUME, REQS, FakeDecider(), emb)
    assert [r.requirement_id for r in results] == [7, 9]


def test_review_no_text_raises():
    with pytest.raises(NoTextError):
        review("   \n ", REQS, FakeDecider(), emb)
