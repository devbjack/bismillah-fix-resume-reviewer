import csv
import io
from pathlib import Path

import pymupdf as fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api import Deps, create_app
from app.req_extract import RequirementsUnavailable
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
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


EXTRACTED = [{"text": "Python", "type": "must"}, {"text": "Docker", "type": "nice"}]


@pytest.fixture
def env(tmp_path):
    store = Store(str(tmp_path / "app.db"))
    uploads = tmp_path / "uploads"
    worker = Worker(store, uploads, FakeDecider(), emb)
    worker.start()
    state = {"extract": lambda text: EXTRACTED}
    deps = Deps(store=store, uploads_dir=uploads, extract=lambda t: state["extract"](t), worker=worker)
    client = TestClient(create_app(deps))
    return client, state, worker, uploads, tmp_path


def make_job(client):
    r = client.post("/api/jobs", data={"name": "Backend"}, files={"file": ("job.pdf", pdf_with("Need Python"), "application/pdf")})
    assert r.status_code == 200
    return r.json()["job"]


def confirm(client, job_id, reqs=None):
    reqs = reqs or [{"text": "Python", "type": "must", "weight": 2}, {"text": "Docker", "type": "nice", "weight": 1}]
    return client.put(f"/api/jobs/{job_id}/requirements", json=reqs)


def upload(client, job_id, files):
    return client.post(f"/api/jobs/{job_id}/resumes", files=[("files", f) for f in files])


def test_create_job_extracts_requirements(env):
    client, *_ = env
    r = client.post("/api/jobs", data={"name": "Backend"}, files={"file": ("job.pdf", pdf_with("Need Python"), "application/pdf")})
    body = r.json()
    assert body["warning"] is None
    job = body["job"]
    assert job["status"] == "draft" and job["name"] == "Backend"
    assert [(q["text"], q["type"], q["weight"]) for q in job["requirements"]] == [("Python", "must", 2), ("Docker", "nice", 1)]


def test_create_job_rejects_non_pdf(env):
    client, *_ = env
    r = client.post("/api/jobs", data={"name": "B"}, files={"file": ("job.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_create_job_ollama_down(env):
    client, state, *_ = env

    def down(text):
        raise RequirementsUnavailable()
    state["extract"] = down
    body = client.post("/api/jobs", data={"name": "B"}, files={"file": ("job.pdf", pdf_with("x"), "application/pdf")}).json()
    assert body["job"]["requirements"] == []
    assert body["warning"] == "Couldn't reach Ollama — start it, or type the requirements yourself."


def test_put_requirements_confirms(env):
    client, *_ = env
    job = make_job(client)
    r = confirm(client, job["id"])
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_put_empty_requirements_rejected(env):
    client, *_ = env
    job = make_job(client)
    assert client.put(f"/api/jobs/{job['id']}/requirements", json=[]).status_code == 400


@pytest.mark.parametrize("reqs", [
    [{"text": "x" * 201, "type": "must", "weight": 2}],
    [{"text": f"r{i}", "type": "must", "weight": 2} for i in range(21)],
    [{"text": "Go", "type": "optional", "weight": 2}],
    [{"text": "Go", "type": "must", "weight": 0}],
    [{"text": "   ", "type": "must", "weight": 2}],
])
def test_put_invalid_requirements_rejected(env, reqs):
    client, *_ = env
    job = make_job(client)
    assert client.put(f"/api/jobs/{job['id']}/requirements", json=reqs).status_code == 422


def test_upload_before_confirm_rejected(env):
    client, *_ = env
    job = make_job(client)
    r = upload(client, job["id"], [("a.pdf", pdf_with("Python"), "application/pdf")])
    assert r.status_code == 409
    assert r.json()["detail"] == "Confirm the requirements first"


def test_upload_mixed_files(env):
    client, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    big = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1)
    r = upload(client, job["id"], [
        ("good.pdf", pdf_with("Python"), "application/pdf"),
        ("notes.txt", b"hello", "text/plain"),
        ("big.pdf", big, "application/pdf"),
    ])
    body = r.json()
    assert [a["filename"] for a in body["accepted"]] == ["good.pdf"]
    assert sorted(x["filename"] for x in body["rejected"]) == ["big.pdf", "notes.txt"]
    assert all(x["filename"] in x["reason"] for x in body["rejected"])


def test_upload_over_100_files_rejected(env):
    client, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    data = pdf_with("Python")
    r = upload(client, job["id"], [(f"r{i}.pdf", data, "application/pdf") for i in range(101)])
    assert r.status_code == 400


def test_upload_filename_is_only_a_label(env):
    client, _, worker, uploads, tmp_path = env
    job = make_job(client)
    confirm(client, job["id"])
    r = upload(client, job["id"], [("../../evil.pdf", pdf_with("Python"), "application/pdf")])
    a = r.json()["accepted"][0]
    assert (uploads / str(job["id"]) / f"{a['id']}.pdf").exists()
    assert not (tmp_path.parent / "evil.pdf").exists()
    assert not (tmp_path / "evil.pdf").exists()
    worker.join_idle(10)
    assert client.get(f"/api/applicants/{a['id']}").json()["filename"] == "../../evil.pdf"


def test_status_and_ranking_after_processing(env):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    upload(client, job["id"], [("a.pdf", pdf_with("Docker only"), "application/pdf"),
                               ("b.pdf", pdf_with("Python and Docker"), "application/pdf")])
    worker.join_idle(10)
    assert client.get(f"/api/jobs/{job['id']}/status").json() == {"done": 2, "total": 2}
    rows = client.get(f"/api/jobs/{job['id']}/ranking").json()
    assert [r["filename"] for r in rows] == ["b.pdf", "a.pdf"]
    assert rows[0]["score"] == 90 and rows[1]["flagged"] is True


def test_put_requirements_requeues_applicants(env):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    a = upload(client, job["id"], [("a.pdf", pdf_with("Go developer"), "application/pdf")]).json()["accepted"][0]
    worker.join_idle(10)
    confirm(client, job["id"], [{"text": "Go", "type": "must", "weight": 1}])
    worker.join_idle(10)
    new_id = client.get(f"/api/jobs/{job['id']}").json()["requirements"][0]["id"]
    detail = client.get(f"/api/applicants/{a['id']}").json()
    assert detail["status"] == "done" and detail["score"] == 90
    assert [r["requirement_id"] for r in detail["results"]] == [new_id]


def test_applicant_detail(env):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    a = upload(client, job["id"], [("a.pdf", pdf_with("Python dev"), "application/pdf")]).json()["accepted"][0]
    worker.join_idle(10)
    d = client.get(f"/api/applicants/{a['id']}").json()
    assert [(r["text"], r["type"], r["probability"]) for r in d["results"]] == [("Python", "must", 0.9), ("Docker", "nice", 0.1)]
    assert "Python" in d["results"][0]["evidence"]
    assert client.get("/api/applicants/999").status_code == 404


def test_export_csv(env):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    upload(client, job["id"], [("scan.pdf", blank_pdf(), "application/pdf"),
                               ("a.pdf", pdf_with("Python"), "application/pdf")])
    worker.join_idle(10)
    r = client.get(f"/api/jobs/{job['id']}/export.csv")
    assert r.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(r.text.lstrip("﻿"))))
    assert rows[0] == ["rank", "filename", "score", "must_met", "must_total", "flagged", "Python", "Docker", "error"]
    assert rows[1][:3] == ["1", "a.pdf", "63"]
    assert rows[2][1] == "scan.pdf" and rows[2][0] == "" and rows[2][2] == ""
    assert rows[2][-1] == "No text found — scanned PDF?"


def blank_pdf():
    doc = fitz.open()
    doc.new_page()
    return doc.tobytes()


def test_delete_job_removes_files(env):
    client, _, worker, uploads, _ = env
    job = make_job(client)
    confirm(client, job["id"])
    upload(client, job["id"], [("a.pdf", pdf_with("Python"), "application/pdf")])
    worker.join_idle(10)
    assert client.delete(f"/api/jobs/{job['id']}").status_code == 204
    assert not (uploads / str(job["id"])).exists()
    assert client.get(f"/api/jobs/{job['id']}").status_code == 404


def test_spa_fallback(tmp_path, env):
    _, _, worker, uploads, _ = env
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<html>app</html>")
    store = Store(str(tmp_path / "other.db"))
    client = TestClient(create_app(Deps(store, uploads, lambda t: [], worker), static_dir=static))
    assert "app" in client.get("/jobs/1/applicants/2").text
    # path traversal must never serve files outside the build folder
    for url in ("/..%2f..%2fother.db", "/..%2fother.db", "/%2e%2e/%2e%2e/other.db"):
        r = client.get(url)
        assert r.status_code == 200 and r.text == "<html>app</html>", url
    assert client.get("/x%00y").text == "<html>app</html>"
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/json")


def test_export_csv_escapes_formula_cells(env):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"], [{"text": "=SUM(1,1) skills", "type": "must", "weight": 1}])
    upload(client, job["id"], [("=HYPERLINK(evil).pdf", pdf_with("Python"), "application/pdf")])
    worker.join_idle(10)
    rows = list(csv.reader(io.StringIO(client.get(f"/api/jobs/{job['id']}/export.csv").text.lstrip("﻿"))))
    assert rows[0][6] == "'=SUM(1,1) skills"
    assert rows[1][1] == "'=HYPERLINK(evil).pdf"


def test_upload_write_failure_marks_failed_and_scores_the_rest(env, monkeypatch):
    client, _, worker, *_ = env
    job = make_job(client)
    confirm(client, job["id"])
    real_write = Path.write_bytes
    calls = []

    def flaky_write(self, data):
        calls.append(self.name)
        if len(calls) == 2:
            raise OSError("disk full")
        return real_write(self, data)
    monkeypatch.setattr(Path, "write_bytes", flaky_write)
    body = upload(client, job["id"], [(f"{n}.pdf", pdf_with("Python"), "application/pdf") for n in ("a", "b", "c")]).json()
    monkeypatch.undo()
    assert [a["filename"] for a in body["accepted"]] == ["a.pdf", "c.pdf"]
    assert body["rejected"] == [{"filename": "b.pdf", "reason": "b.pdf could not be saved: disk full"}]
    worker.join_idle(10)
    statuses = {r["filename"]: r["status"] for r in client.get(f"/api/jobs/{job['id']}/ranking").json()}
    assert statuses == {"a.pdf": "done", "b.pdf": "failed", "c.pdf": "done"}


def test_create_job_from_scanned_pdf_warns(env):
    client, *_ = env
    body = client.post("/api/jobs", data={"name": "B"}, files={"file": ("scan.pdf", blank_pdf(), "application/pdf")}).json()
    assert body["job"]["requirements"] == []
    assert body["warning"] == "No text found in this PDF — type the requirements yourself."
