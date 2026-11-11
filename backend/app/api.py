import csv
import io
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, Literal

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints

from app.pdf_text import extract_text, is_pdf
from app.req_extract import RequirementsUnavailable
from app.store import Store
from app.worker import Worker

MAX_FILES = 100
MAX_BYTES = 10 * 1024 * 1024
DEFAULT_WEIGHT = {"must": 2, "nice": 1}
OLLAMA_DOWN = "Couldn't reach Ollama — start it, or type the requirements yourself."
NO_JOB_TEXT = "No text found in this PDF — type the requirements yourself."


@dataclass
class Deps:
    store: Store
    uploads_dir: Path
    extract: Callable[[str], list[dict]]
    worker: Worker


class RequirementIn(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    type: Literal["must", "nice"]
    weight: float = Field(gt=0)


def _cell(value):
    """Stop Excel from running applicant-controlled text (file names) as a formula."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", chr(9), chr(13)):  # tab, CR
        return "'" + value
    return value


def _public_job(job: dict) -> dict:
    return {k: v for k, v in job.items() if k != "job_text"}


def _with_rank(rows: list[dict]) -> list[dict]:
    rank = 0
    for row in rows:
        if row["status"] == "done":
            rank += 1
            row["rank"] = rank
        else:
            row["rank"] = None
    return rows


def create_app(deps: Deps, static_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI Resume Reviewer")
    store = deps.store

    def job_or_404(job_id: int) -> dict:
        job = store.get_job(job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job

    # Endpoints are sync on purpose: FastAPI runs them in a thread pool, so the
    # Ollama call and file reads don't block the event loop.
    @app.post("/api/jobs")
    def create_job(name: Annotated[str, Form(min_length=1, max_length=120)], file: UploadFile = File(...)):
        data = file.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or not is_pdf(data):
            raise HTTPException(400, f"{file.filename}: not a readable PDF of 10 MB or less")
        job_text = extract_text(data)
        job_id = store.create_job(name.strip(), job_text)
        reqs, warning = [], NO_JOB_TEXT
        if job_text.strip():
            try:
                reqs, warning = deps.extract(job_text), None
            except RequirementsUnavailable:
                warning = OLLAMA_DOWN
        store.set_requirements(job_id, [{**r, "weight": DEFAULT_WEIGHT[r["type"]]} for r in reqs], confirm=False)
        return {"job": _public_job(store.get_job(job_id)), "warning": warning}

    @app.get("/api/jobs")
    def list_jobs():
        return store.list_jobs()

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: int):
        return _public_job(job_or_404(job_id))

    @app.put("/api/jobs/{job_id}/requirements")
    def put_requirements(job_id: int, reqs: Annotated[list[RequirementIn], Field(max_length=20)]):
        job_or_404(job_id)
        if not reqs:
            raise HTTPException(400, "Add at least one requirement")
        store.set_requirements(job_id, [r.model_dump() for r in reqs])
        deps.worker.enqueue(store.requeue_job(job_id))
        return _public_job(store.get_job(job_id))

    @app.post("/api/jobs/{job_id}/resumes")
    def upload_resumes(job_id: int, files: list[UploadFile] = File(...)):
        job = job_or_404(job_id)
        if job["status"] != "confirmed":
            raise HTTPException(409, "Confirm the requirements first")
        if len(files) > MAX_FILES:
            raise HTTPException(400, f"Upload at most {MAX_FILES} files at once")
        accepted, rejected = [], []
        folder = deps.uploads_dir / str(job_id)
        folder.mkdir(parents=True, exist_ok=True)
        for f in files:
            name = f.filename or "unnamed.pdf"
            data = f.file.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                rejected.append({"filename": name, "reason": f"{name} is larger than 10 MB"})
            elif not is_pdf(data):
                rejected.append({"filename": name, "reason": f"{name} is not a readable PDF"})
            else:
                applicant_id = store.add_applicant(job_id, name)
                try:
                    # the original name is only a label; the disk path comes from the id
                    (folder / f"{applicant_id}.pdf").write_bytes(data)
                except OSError as e:
                    store.mark_failed(applicant_id, f"Could not save the file: {e}")
                    rejected.append({"filename": name, "reason": f"{name} could not be saved: {e}"})
                    continue
                deps.worker.enqueue([applicant_id])
                accepted.append({"id": applicant_id, "filename": name})
        return {"accepted": accepted, "rejected": rejected}

    @app.get("/api/jobs/{job_id}/status")
    def status(job_id: int):
        job_or_404(job_id)
        return store.status(job_id)

    @app.get("/api/jobs/{job_id}/ranking")
    def ranking(job_id: int):
        job_or_404(job_id)
        return _with_rank(store.ranking(job_id))

    @app.get("/api/jobs/{job_id}/summary")
    def summary(job_id: int):
        job_or_404(job_id)
        return store.summary(job_id)

    @app.get("/api/applicants/{applicant_id}")
    def applicant(applicant_id: int):
        app_ = store.get_applicant(applicant_id)
        if app_ is None:
            raise HTTPException(404, "Applicant not found")
        return app_

    @app.get("/api/jobs/{job_id}/export.csv")
    def export_csv(job_id: int):
        job = job_or_404(job_id)
        reqs = job["requirements"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rank", "filename", "score", "must_met", "must_total", "flagged", *[_cell(r["text"]) for r in reqs], "error"])
        for row in _with_rank(store.ranking(job_id)):
            probs = {r["requirement_id"]: r["probability"] for r in store.get_applicant(row["id"])["results"]}
            done = row["status"] == "done"
            w.writerow([
                row["rank"] or "", _cell(row["filename"]),
                row["score"] if done else "", row["must_met"] if done else "", row["must_total"] if done else "",
                ("yes" if row["flagged"] else "no") if done else "",
                *[f"{probs[r['id']]:.2f}" if r["id"] in probs else "" for r in reqs],
                _cell(row["error"]) or ("queued" if row["status"] == "queued" else ""),
            ])
        # BOM so Excel opens the UTF-8 file correctly
        return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="job-{job_id}-ranking.csv"'})

    @app.delete("/api/jobs/{job_id}", status_code=204)
    def delete_job(job_id: int):
        job_or_404(job_id)
        store.delete_job(job_id)
        shutil.rmtree(deps.uploads_dir / str(job_id), ignore_errors=True)
        return Response(status_code=204)

    if static_dir is not None and (static_dir / "index.html").is_file():
        root = static_dir.resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path == "api" or path.startswith("api/"):
                raise HTTPException(404, "Not found")
            try:
                file = (root / path).resolve()
                if path and file.is_file() and file.is_relative_to(root):
                    return FileResponse(file)
            except (ValueError, OSError):  # e.g. a null byte in the URL
                pass
            return FileResponse(root / "index.html")

    return app
