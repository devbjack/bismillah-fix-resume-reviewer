import pymupdf as fitz
import numpy as np
import pytest

from app.store import Store
from app.worker import Worker


class FakeDecider:
    def p_met(self, requirement, evidence):
        word = requirement.split()[0].lower()
        return 0.9 if any(word in e.lower() for e in evidence) else 0.1


def emb(texts):
    return np.ones((len(texts), 3))


def pdf_with(text):
    doc = fitz.open()
    page = doc.new_page()
    if text:
        page.insert_text((72, 72), text)
    return doc.tobytes()


@pytest.fixture
def env(tmp_path):
    store = Store(str(tmp_path / "app.db"))
    uploads = tmp_path / "uploads"
    job = store.create_job("J", "t")
    store.set_requirements(job, [{"text": "Python", "type": "must", "weight": 2}])
    worker = Worker(store, uploads, FakeDecider(), emb)

    def add(name, data):
        a = store.add_applicant(job, name)
        (uploads / str(job)).mkdir(parents=True, exist_ok=True)
        (uploads / str(job) / f"{a}.pdf").write_bytes(data)
        return a

    return store, worker, job, add


def test_worker_scores_queued_applicant(env):
    store, worker, job, add = env
    a = add("a.pdf", pdf_with("Python developer"))
    worker.start()
    worker.enqueue([a])
    worker.join_idle(10)
    app = store.get_applicant(a)
    assert app["status"] == "done" and app["score"] == 90
    assert len(app["results"]) == 1


def test_worker_marks_scanned_pdf_failed(env):
    store, worker, job, add = env
    a = add("scan.pdf", pdf_with(""))
    worker.process(a)
    app = store.get_applicant(a)
    assert app["status"] == "failed"
    assert app["error"] == "No text found — scanned PDF?"


def test_worker_marks_failed_and_continues(env):
    store, worker, job, add = env
    bad = add("bad.pdf", b"%PDF-garbage")
    good = add("good.pdf", pdf_with("Python"))
    worker.start()
    worker.enqueue([bad, good])
    worker.join_idle(10)
    assert store.get_applicant(bad)["status"] == "failed"
    assert store.get_applicant(bad)["error"] == "Not a readable PDF"
    assert store.get_applicant(good)["status"] == "done"


def test_start_picks_up_queued_from_previous_run(env):
    store, worker, job, add = env
    a = add("a.pdf", pdf_with("Python"))  # left queued, never enqueued
    worker.start()
    worker.join_idle(10)
    assert store.get_applicant(a)["status"] == "done"


def test_process_reads_requirements_at_process_time(env):
    store, worker, job, add = env
    a = add("a.pdf", pdf_with("Go developer"))
    store.set_requirements(job, [{"text": "Go", "type": "must", "weight": 1}])
    worker.process(a)
    new_id = store.get_job(job)["requirements"][0]["id"]
    assert [r["requirement_id"] for r in store.get_applicant(a)["results"]] == [new_id]


def test_edit_mid_scoring_never_saves_stale_result(env):
    store, worker, job, add = env
    a = add("a.pdf", pdf_with("Python developer"))

    class EditingDecider:
        """Simulates HR saving new requirements while this resume is being scored."""
        def __init__(self):
            self.edited = False

        def p_met(self, requirement, evidence):
            if not self.edited:
                self.edited = True
                store.set_requirements(job, [{"text": "Go", "type": "must", "weight": 1}])
                store.requeue_job(job)
            return 0.9

    worker.decider = EditingDecider()
    worker.process(a)
    app = store.get_applicant(a)
    assert app["status"] == "queued" and app["results"] == [] and app["error"] is None
    worker.process(a)  # the requeued run scores against the new list
    new_id = store.get_job(job)["requirements"][0]["id"]
    assert [r["requirement_id"] for r in store.get_applicant(a)["results"]] == [new_id]


def test_decider_unavailable_gives_clear_message(env):
    from app.decider import DeciderUnavailable
    store, worker, job, add = env
    a = add("a.pdf", pdf_with("Python developer"))

    class Down:
        def p_met(self, requirement, evidence):
            raise DeciderUnavailable("refused")

    worker.decider = Down()
    worker.process(a)
    assert store.get_applicant(a)["error"] == "Couldn't reach Ollama — start it, then save the requirements again to re-score."
