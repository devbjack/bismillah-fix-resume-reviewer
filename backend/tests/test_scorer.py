import pytest

from app.scorer import ScoreResult, score


def test_weighted_score():
    assert score([("must", 2, 0.9), ("nice", 1, 0.3)]).score == 70  # (1.8+0.3)/3


def test_must_met_and_flag():
    r = score([("must", 2, 0.5), ("must", 2, 0.49), ("nice", 1, 0.1)])
    assert (r.must_met, r.must_total, r.flagged) == (1, 2, True)


def test_all_musts_met_not_flagged():
    assert score([("must", 2, 0.8), ("nice", 1, 0.0)]).flagged is False


def test_no_must_haves_not_flagged():
    assert score([("nice", 1, 0.2)]) == ScoreResult(20, 0, 0, False)


def test_empty_raises():
    with pytest.raises(ValueError):
        score([])
