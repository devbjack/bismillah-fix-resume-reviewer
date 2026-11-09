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
