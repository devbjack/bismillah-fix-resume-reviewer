import pytest

from app.pipeline import ReqResult
from app.scorer import ScoreResult
from app.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "app.db"))


REQS = [
    {"text": "Python", "type": "must", "weight": 2},
    {"text": "Docker", "type": "nice", "weight": 1},
]


def done(store, job, name, score, must_met):
    a = store.add_applicant(job, name)
    req_ids = [r["id"] for r in store.get_job(job)["requirements"]]
    store.save_result(a, ScoreResult(score, must_met, 2, must_met < 2),
                      [ReqResult(req_ids[0], 0.9, "ev1"), ReqResult(req_ids[1], 0.2, "ev2")])
    return a


def test_job_roundtrip_and_confirm(store):
    job = store.create_job("Backend", "job text")
    assert store.get_job(job)["status"] == "draft"
    store.set_requirements(job, REQS)
    j = store.get_job(job)
    assert j["status"] == "confirmed"
    assert [(r["text"], r["type"], r["weight"]) for r in j["requirements"]] == [("Python", "must", 2), ("Docker", "nice", 1)]
    assert all("id" in r for r in j["requirements"])
    assert [x["id"] for x in store.list_jobs()] == [job]


def test_get_missing_returns_none(store):
    assert store.get_job(999) is None
    assert store.get_applicant(999) is None


def test_ranking_order(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    done(store, job, "a.pdf", 70, 1)
    done(store, job, "b.pdf", 70, 2)
    done(store, job, "c.pdf", 90, 0)
    store.add_applicant(job, "queued.pdf")
    f = store.add_applicant(job, "failed.pdf")
    store.mark_failed(f, "No text found — scanned PDF?")
    names = [r["filename"] for r in store.ranking(job)]
    assert names == ["c.pdf", "b.pdf", "a.pdf", "queued.pdf", "failed.pdf"]


def test_ranking_tiebreak_filename(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    done(store, job, "zed.pdf", 50, 1)
    done(store, job, "amy.pdf", 50, 1)
    assert [r["filename"] for r in store.ranking(job)] == ["amy.pdf", "zed.pdf"]


def test_status_counts_done_and_failed(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    done(store, job, "a.pdf", 50, 1)
    f = store.add_applicant(job, "b.pdf")
    store.mark_failed(f, "x")
    store.add_applicant(job, "c.pdf")
    assert store.status(job) == {"done": 2, "total": 3}
    assert store.queued_ids() == [f + 1]


def test_get_applicant_includes_results(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    a = done(store, job, "a.pdf", 50, 1)
    app = store.get_applicant(a)
    assert app["status"] == "done" and app["score"] == 50
    assert [(r["text"], r["type"], r["probability"], r["evidence"]) for r in app["results"]] == [
        ("Python", "must", 0.9, "ev1"), ("Docker", "nice", 0.2, "ev2")]


def test_save_result_replaces_previous_results(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    a = done(store, job, "a.pdf", 50, 1)
    rid = store.get_job(job)["requirements"][0]["id"]
    store.save_result(a, ScoreResult(10, 0, 1, True), [ReqResult(rid, 0.1, "new")])
    assert [(r["probability"], r["evidence"]) for r in store.get_applicant(a)["results"]] == [(0.1, "new")]


def test_requeue_clears_scores_and_results(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    a = done(store, job, "a.pdf", 50, 1)
    f = store.add_applicant(job, "b.pdf")
    store.mark_failed(f, "x")
    assert sorted(store.requeue_job(job)) == [a, f]
    app = store.get_applicant(a)
    assert (app["status"], app["score"], app["results"]) == ("queued", None, [])
    assert store.get_applicant(f)["error"] is None


def test_set_requirements_replaces_rows(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    store.set_requirements(job, [{"text": "Go", "type": "must", "weight": 3}])
    assert [r["text"] for r in store.get_job(job)["requirements"]] == ["Go"]


def test_delete_job_cascades(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    a = done(store, job, "a.pdf", 50, 1)
    store.delete_job(job)
    assert store.get_job(job) is None
    assert store.get_applicant(a) is None
    assert store.list_jobs() == []


def test_set_requirements_draft_keeps_status(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS, confirm=False)
    j = store.get_job(job)
    assert j["status"] == "draft" and len(j["requirements"]) == 2


def test_requirement_ids_never_reused(store):
    job = store.create_job("J", "t")
    store.set_requirements(job, REQS)
    old = {r["id"] for r in store.get_job(job)["requirements"]}
    store.set_requirements(job, REQS)
    new = {r["id"] for r in store.get_job(job)["requirements"]}
    assert old.isdisjoint(new)


# --- summary -----------------------------------------------------------------

FOUR = [{"text": f"M{i}", "type": "must", "weight": 2} for i in range(2)] + [{"text": "N1", "type": "nice", "weight": 1}]


def scored(store, job, name, score, probs):
    """Save a scored applicant; must_met is derived from the job's requirement types."""
    reqs = store.get_job(job)["requirements"]
    a = store.add_applicant(job, name)
    musts = [p for r, p in zip(reqs, probs) if r["type"] == "must"]
    met = sum(p >= 0.5 for p in musts)
    store.save_result(a, ScoreResult(score, met, len(musts), met < len(musts)),
                      [ReqResult(r["id"], p, "ev") for r, p in zip(reqs, probs)])
    return a


def job_with(store, reqs=FOUR):
    job = store.create_job("J", "t")
    store.set_requirements(job, reqs)
    return job


def test_summary_empty_job(store):
    s = store.summary(job_with(store))
    assert (s["total"], s["scored"], s["queued"], s["failed"], s["qualified"]) == (0, 0, 0, 0, 0)
    assert s["average_score"] is None and s["best"] is None and s["top"] == []
    assert s["histogram"] == [0] * 10
    assert [(c["text"], c["met"], c["scored"]) for c in s["coverage"]] == [("M0", 0, 0), ("M1", 0, 0), ("N1", 0, 0)]


def test_summary_counts_by_status(store):
    job = job_with(store)
    scored(store, job, "a.pdf", 80, [0.9, 0.9, 0.9])
    scored(store, job, "b.pdf", 40, [0.1, 0.9, 0.9])
    store.add_applicant(job, "queued.pdf")
    store.mark_failed(store.add_applicant(job, "bad.pdf"), "x")
    s = store.summary(job)
    assert (s["total"], s["scored"], s["queued"], s["failed"]) == (4, 2, 1, 1)


def test_summary_qualified_needs_every_must(store):
    job = job_with(store)
    scored(store, job, "a.pdf", 70, [0.5, 0.9, 0.1])
    scored(store, job, "b.pdf", 80, [0.9, 0.49, 0.9])
    assert store.summary(job)["qualified"] == 1


def test_summary_no_musts_all_scored_qualify(store):
    job = job_with(store, [{"text": "N1", "type": "nice", "weight": 1}])
    scored(store, job, "a.pdf", 90, [0.9])
    scored(store, job, "b.pdf", 10, [0.1])
    s = store.summary(job)
    assert s["qualified"] == s["scored"] == 2


def test_summary_histogram_band_edges(store):
    job = job_with(store)
    for score in (0, 9, 10, 99, 100):
        scored(store, job, f"s{score}.pdf", score, [0.9, 0.9, 0.9])
    assert store.summary(job)["histogram"] == [2, 1, 0, 0, 0, 0, 0, 0, 0, 2]


def test_summary_coverage_counts_and_order(store):
    job = job_with(store, [{"text": "N1", "type": "nice", "weight": 1}, {"text": "M0", "type": "must", "weight": 2}])
    for i, (n1, m0) in enumerate([(0.9, 0.2), (0.9, 0.6), (0.1, 0.7)]):
        scored(store, job, f"a{i}.pdf", 50, [n1, m0])
    store.add_applicant(job, "queued.pdf")
    cov = store.summary(job)["coverage"]
    assert [(c["text"], c["type"], c["met"], c["scored"]) for c in cov] == [("M0", "must", 2, 3), ("N1", "nice", 2, 3)]


def test_summary_top_is_qualified_only_in_rank_order(store):
    job = job_with(store)
    for name, score in [("q90.pdf", 90), ("b.pdf", 80), ("a.pdf", 80), ("q70.pdf", 70), ("q60.pdf", 60), ("q50.pdf", 50), ("q40.pdf", 40)]:
        scored(store, job, name, score, [0.9, 0.9, 0.1])
    scored(store, job, "unq.pdf", 95, [0.1, 0.9, 0.9])
    top = store.summary(job)["top"]
    assert [t["filename"] for t in top] == ["q90.pdf", "a.pdf", "b.pdf", "q70.pdf", "q60.pdf"]
    assert top[0]["must_met"] == top[0]["must_total"] == 2


def test_summary_best_and_average(store):
    job = job_with(store)
    best_id = scored(store, job, "best.pdf", 95, [0.1, 0.9, 0.9])
    scored(store, job, "ok.pdf", 60, [0.9, 0.9, 0.9])
    store.mark_failed(store.add_applicant(job, "bad.pdf"), "x")
    s = store.summary(job)
    assert s["best"] == {"id": best_id, "filename": "best.pdf", "score": 95}
    assert s["average_score"] == 77.5
