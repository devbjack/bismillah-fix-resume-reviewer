# AI Resume Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local web app that ranks resume PDFs against a job-requirement PDF and shows per-requirement probabilities with evidence.

**Architecture:** A FastAPI backend runs the pipeline: PyMuPDF text → chunks → BM25 + bge embeddings fused by RRF → Julia 1 `noul` P(met) per requirement → weighted score, with SQLite storage and one background worker. Ollama extracts requirements from the job PDF once. A Vite React app talks to `/api` and is served by FastAPI after build.

**Tech Stack:** Python 3.11, FastAPI, uvicorn, PyMuPDF, rank-bm25, sentence-transformers (`BAAI/bge-small-en-v1.5`), Julia 1 (`SupersonicLabs/Julia-1`), ollama (`qwen2.5:3b`), sqlite3, pytest · Node 24, Vite, React, TypeScript, Tailwind, react-router.

**Spec:** `docs/superpowers/specs/2026-11-09-ai-resume-reviewer-design.md`

## Global Constraints

- Free and local only: no paid API, no network calls except Ollama on `localhost` and the first-run model downloads.
- English resumes; PDF only; no OCR.
- Requirement text ≤ 200 characters; at most 20 requirements per job.
- Default weights: must = 2, nice = 1.
- Score: `round(100 × Σ(weight × P) / Σ(weight))`; met means P ≥ 0.5; `flagged` = any must-have with P < 0.5.
- Ranking order: score desc, then must_met desc, then filename asc; queued next; failed last.
- RRF: `1/(60 + rank)` summed over BM25 and embedding ranks (ranks start at 1); keep top 3 chunks.
- Chunks: split at blank lines and heading-like lines, merge neighbors up to 1,000 chars, hard-split over 1,500.
- Uploads: ≤ 100 files per request, ≤ 10 MB per file.
- Applicant label = original file name; files are stored on disk as `data/uploads/{job_id}/{applicant_id}.pdf`.
- All user-facing error strings are copied verbatim from spec §8.
- UI design follows `ref/DESIGN.md`. Use its color, typography, radius and spacing tokens; Inter is the font; one filled aubergine pill per view; semantic success/error colors for met/not met. Tasks 10–12 are designed with the `ui-ux-pro-max:ui-ux-pro-max` and `impeccable:impeccable` skills. It's a transactional app, so no marketing hero or pastel-mesh backdrop beyond, at most, a subtle header wash.

## Review Focus

1. **Hostile or odd file names** (`../../x.pdf`, duplicates, unicode): the original name is only a label; disk paths come from the applicant id. → Task 9 test `test_upload_filename_is_only_a_label`.
2. **Requirements edited while scoring runs:** final results reflect only the new requirements, and no stale result rows remain. → Task 7 test `test_save_result_replaces_previous_results`; Task 9 test `test_put_requirements_requeues_applicants`.
3. **Confirming an empty requirement list:** rejected with 400, never a division by zero. → Task 9 test `test_put_empty_requirements_rejected`.
4. **A file named `.pdf` that isn't one, or an encrypted PDF:** rejected at upload (not a PDF) or marked `failed` (can't read); the worker keeps going. → Task 1 test `test_extract_text_rejects_non_pdf`; Task 8 test `test_worker_marks_failed_and_continues`.
5. **A very short resume (one chunk, or fewer than 3):** retrieval returns what exists and scoring still works. → Task 2 test `test_top_returns_all_when_fewer_than_n`.

---

## File Structure

```
.gitignore                     data/, models/, frontend/node_modules, frontend/dist, __pycache__
run.py                         starts uvicorn on backend app (port 8000)
backend/
  requirements.txt
  pytest.ini                   markers: slow
  app/
    pdf_text.py                extract_text, is_pdf
    chunker.py                 chunk_text
    retriever.py               rrf_fuse, ResumeIndex
    scorer.py                  ScoreResult, score
    decider.py                 Decider protocol, JuliaDecider
    req_extract.py             extract_requirements, RequirementsUnavailable
    pipeline.py                ReqResult, NoTextError, review
    store.py                   Store (sqlite)
    worker.py                  Worker
    api.py                     create_app(deps)
    main.py                    builds real deps, `app`
  tests/                       one test file per module
scripts/
  download_models.py           fetches Julia-1 into models/Julia-1
  make_samples.py              builds samples/*.pdf from samples/src/*.txt
  validate.py                  Step 0 gate report
samples/
  src/job.txt, src/r01..r10.txt
  labels.json
frontend/                      Vite react-ts app
  src/api.ts                   typed fetch client
  src/pages/JobsPage.tsx
  src/pages/JobPage.tsx
  src/components/RequirementsEditor.tsx
  src/components/ResumeUpload.tsx
  src/components/ApplicantList.tsx
  src/components/ApplicantReview.tsx
```

The spec's `requirements` module is named `req_extract.py` here, so it can't be confused with `requirements.txt`.

---

### Task 1: Repo scaffold, PDF text, chunker

**Files:**
- Create: `.gitignore`, `backend/requirements.txt`, `backend/pytest.ini`, `backend/app/__init__.py`, `backend/app/pdf_text.py`, `backend/app/chunker.py`
- Test: `backend/tests/test_pdf_text.py`, `backend/tests/test_chunker.py`

**Interfaces:**
- Produces: `is_pdf(data: bytes) -> bool`; `extract_text(data: bytes) -> str` (raises `ValueError("Not a readable PDF")`); `chunk_text(text: str, target: int = 1000, hard_max: int = 1500) -> list[str]`

- [ ] **Step 1: `git init`, write `.gitignore`, `backend/requirements.txt`** (fastapi, uvicorn, python-multipart, pymupdf, rank-bm25, sentence-transformers, ollama, numpy, pytest, httpx) and `pytest.ini` (register marker `slow`, default `-m "not slow"`). Create venv `backend/.venv` and install.
- [ ] **Step 2: Write failing tests**

```python
# test_pdf_text.py — build PDFs in-test with fitz.open(); page.insert_text(...)
def test_extract_text_returns_page_text(): assert "Python developer" in extract_text(pdf_with("Python developer"))
def test_extract_text_empty_for_imageonly_pdf(): assert extract_text(blank_page_pdf()).strip() == ""
def test_extract_text_rejects_non_pdf():
    with pytest.raises(ValueError): extract_text(b"hello, I am a .docx")
def test_is_pdf(): assert is_pdf(pdf_with("x")) and not is_pdf(b"PK\x03\x04")

# test_chunker.py
def test_splits_on_blank_lines_and_merges_small(): # 3 paragraphs of 300 chars → 1 chunk (≤1000)
def test_new_chunk_when_target_exceeded():         # 3 paragraphs of 600 chars → 3 chunks
def test_heading_line_starts_new_paragraph():      # "EXPERIENCE\nBackend Engineer..." splits before EXPERIENCE (an ALL-CAPS line ≤ 40 chars, or a line ending with ":")
def test_hard_splits_long_paragraph(): assert all(len(c) <= 1500 for c in chunk_text("a " * 2000))
def test_empty_text(): assert chunk_text("  \n ") == []
```

- [ ] **Step 3: Run** `cd backend && .venv/Scripts/python -m pytest tests/test_pdf_text.py tests/test_chunker.py` → FAIL (import errors).
- [ ] **Step 4: Implement** `pdf_text.py` with `fitz.open(stream=data, filetype="pdf")` and `page.get_text(sort=True)` (reading order by position, which helps two-column resumes); any open error or `doc.needs_pass` → `ValueError("Not a readable PDF")`. `is_pdf` checks the `%PDF` prefix and that it opens. `chunker.py`: paragraphs → greedy merge up to `target` → hard-split oversized ones at whitespace.
- [ ] **Step 5: Run tests** → PASS.
- [ ] **Step 6: Commit** `feat: scaffold backend, pdf text and chunker`

### Task 2: Retriever (BM25 + embeddings + RRF)

**Files:** Create `backend/app/retriever.py` · Test `backend/tests/test_retriever.py`

**Interfaces:**
- Consumes: chunks from `chunk_text`
- Produces: `Embed = Callable[[list[str]], numpy.ndarray]` (rows L2-normalized); `rrf_fuse(rankings: list[list[int]], k: int = 60) -> list[int]` (each ranking = indices best-first; returns indices best-first); `class ResumeIndex(chunks: list[str], embed: Embed)` with `.top(requirement: str, n: int = 3) -> list[str]`; `QUERY_PREFIX = "Represent this sentence for searching relevant passages: "`

- [ ] **Step 1: Write failing tests**

```python
def test_rrf_fuse_prefers_item_ranked_well_in_both(): assert rrf_fuse([[0,1,2],[1,2,0]])[0] == 1   # 1/62+1/61 > 1/61+1/63
def test_rrf_fuse_exact_scores(): # [[2,0,1],[0,2,1]] → 0 and 2 tie at 1/61+1/62; ties keep lower index first → [0,2,1]
def test_top_finds_keyword_chunk(): # fake embed returns identical vectors → BM25 decides; "PostgreSQL" chunk returned first
def test_top_uses_embeddings(): # fake embed makes chunk 2 closest to the query; BM25 has no overlap → chunk 2 first
def test_top_returns_all_when_fewer_than_n(): assert ResumeIndex(["only one"], fake).top("Python", 3) == ["only one"]
def test_embeds_chunks_once(): # counting fake embed: 3 calls to .top → chunks embedded 1 time, queries 3 times
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `ResumeIndex.__init__` builds `BM25Okapi` over lowercase `\w+` tokens and embeds the chunks once. `top()` embeds `QUERY_PREFIX + requirement`; BM25 ranking = argsort of `get_scores` desc; embedding ranking = argsort of dot product desc; `rrf_fuse` then picks the first `n`. Sorting is stable, so ties keep the lower index first.
- [ ] **Step 4: Run** → PASS. **Step 5: Commit** `feat: add RRF retriever`

### Task 3: Scorer

**Files:** Create `backend/app/scorer.py` · Test `backend/tests/test_scorer.py`

**Interfaces:**
- Produces: `@dataclass ScoreResult(score: int, must_met: int, must_total: int, flagged: bool)`; `score(items: list[tuple[str, float, float]]) -> ScoreResult` where each item = `(type "must"|"nice", weight, probability)`; raises `ValueError` on an empty list.

- [ ] **Step 1: Write failing tests**

```python
def test_weighted_score(): assert score([("must",2,0.9),("nice",1,0.3)]).score == 70   # (1.8+0.3)/3
def test_must_met_and_flag(): r = score([("must",2,0.5),("must",2,0.49),("nice",1,0.1)]); assert (r.must_met, r.must_total, r.flagged) == (1,2,True)
def test_no_must_haves_not_flagged(): assert score([("nice",1,0.2)]) == ScoreResult(20,0,0,False)
def test_empty_raises(): pytest.raises(ValueError, score, [])
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat: add scorer`

### Task 4: Julia decider + model download

**Files:** Create `scripts/download_models.py`, `backend/app/decider.py` · Test `backend/tests/test_decider.py`

**Interfaces:**
- Produces: `class Decider(Protocol): def p_met(self, requirement: str, evidence: list[str]) -> float`; `class JuliaDecider(model_dir: str, device: str = "cpu")`; `MODEL_DIR = "models/Julia-1"` (relative to repo root)

- [ ] **Step 1: Write and run `scripts/download_models.py`**: `snapshot_download("SupersonicLabs/Julia-1", local_dir="models/Julia-1")`, then `pip install -e models/Julia-1` into `backend/.venv`. Check that `models/Julia-1/model.safetensors` is about 550 MB (not an LFS pointer). If installing Julia conflicts with the `transformers` version pulled in by sentence-transformers, stop and report the conflict.
- [ ] **Step 2: Write the failing slow test**

```python
@pytest.mark.slow
def test_julia_separates_met_from_unmet():
    d = JuliaDecider(MODEL_DIR)
    yes = d.p_met("3+ years of professional Python experience", ["Backend Engineer, 2019–2024. Built Python services with Django and FastAPI."])
    no  = d.p_met("3+ years of professional Python experience", ["Graphic designer. Adobe Illustrator, branding, print layouts."])
    assert 0.0 <= no < yes <= 1.0
```

- [ ] **Step 3: Run** `pytest -m slow tests/test_decider.py` → FAIL.
- [ ] **Step 4: Implement `JuliaDecider`.** Load once with `load_model(model_dir, device=device, strict_encoding=True, max_length=2048, head_length=512)`. `p_met` calls `engine.predict(state="\n\n".join(evidence), questions={"met": {"type": "noul", "instructions": f"Does the candidate meet this requirement: {requirement}?", "criteria": {"false": "The text does not show the candidate meets this requirement", "true": "The text shows the candidate meets this requirement"}}})` and returns `float(result["answers"]["met"]["noul"])`.
- [ ] **Step 5: Run** → PASS. Record the per-call time printed by `pytest -s --durations=0` in the commit message.
- [ ] **Step 6: Commit** `feat: add Julia decider`

### Task 5: Requirement extraction (Ollama)

**Files:** Create `backend/app/req_extract.py` · Test `backend/tests/test_req_extract.py`

**Interfaces:**
- Produces: `class RequirementsUnavailable(Exception)`; `extract_requirements(job_text: str, chat: Callable[..., Any] | None = None, model: str = "qwen2.5:3b") -> list[dict]` returning `[{"text": str, "type": "must"|"nice"}]`. `chat` defaults to `ollama.Client().chat`; tests inject a fake.

- [ ] **Step 1: Write failing tests** (fake `chat` returns an object with `.message.content`):

```python
def test_parses_schema_output(): # content '{"requirements":[{"text":"Python","type":"must"}]}' → [{"text":"Python","type":"must"}]
def test_clips_text_and_count(): # 25 items with 300-char text → 20 items, each text len 200
def test_drops_bad_items():      # type "optional" or empty text dropped
def test_passes_schema_and_temperature_zero(): # captured kwargs: format == SCHEMA, options["temperature"] == 0
def test_connection_error_raises_unavailable(): # chat raises ConnectionError → RequirementsUnavailable
def test_invalid_json_returns_empty(): assert extract_requirements("x", chat=fake("not json")) == []
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** `SCHEMA` = a JSON schema object with property `requirements` (an array of `{text: string, type: enum[must, nice]}`). System prompt: "Extract the job requirements as short, single-skill statements. Mark as 'must' anything stated as required; mark 'nice' anything stated as preferred, a plus, or nice to have." Any exception from `chat` → `RequirementsUnavailable`.
- [ ] **Step 4: Run** → PASS. Then do a manual check with Ollama running: `ollama pull qwen2.5:3b`, then call it on `samples/src/job.txt` once Task 6 has created that file (or on any job text now).
- [ ] **Step 5: Commit** `feat: add requirement extraction via Ollama`

### Task 6: Pipeline + samples + Step 0 validation gate

**Files:** Create `backend/app/pipeline.py`, `scripts/make_samples.py`, `scripts/validate.py`, `samples/src/job.txt`, `samples/src/r01.txt`…`r10.txt`, `samples/labels.json` · Test `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: `chunk_text`, `ResumeIndex`, `Decider`, `score`
- Produces: `class NoTextError(Exception)`; `@dataclass ReqResult(requirement_id: int, probability: float, evidence: str)`; `review(text: str, requirements: list[dict], decider: Decider, embed: Embed) -> tuple[ScoreResult, list[ReqResult]]`, where each requirement dict has `id, text, type, weight`.

- [ ] **Step 1: Write failing tests** (fake decider returns 0.9 if the requirement's first word appears in the evidence, else 0.1; fake embed = constant vectors):

```python
def test_review_scores_and_returns_evidence(): # resume mentions Python not Docker; reqs Python(must,2), Docker(nice,1) → score 63, results[0].evidence contains "Python"
def test_review_no_text_raises(): pytest.raises(NoTextError, review, "   ", reqs, dec, emb)
def test_review_one_result_per_requirement_in_order(): assert [r.requirement_id for r in results] == [r["id"] for r in reqs]
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement `review`** (evidence = the top-ranked chunk). **Step 4: Run** → PASS.
- [ ] **Step 5: Write sample data.** `job.txt`: "Backend Developer" with 4 must-haves (3+ years professional Python; SQL databases such as PostgreSQL or MySQL; designing REST APIs; Bachelor's in Computer Science or related) and 4 nice-to-haves (Docker; a cloud platform such as AWS, GCP or Azure; CI/CD pipelines; automated testing). Ten fictional English resumes: r01–r03 strong, r04–r07 medium, r08–r10 weak; at least one where "3+ years" must be summed across two jobs. At least 3 resumes use a two-column layout (a skills sidebar beside the experience column); mark them in their source with a `---COLUMN---` separator. `make_samples.py` writes `samples/job.pdf`, `samples/r01.pdf`…`r10.pdf`, plus `samples/r11_scanned.pdf` (render r01 to a pixmap and insert it as an image-only page).
- [ ] **Step 6: Draft `samples/labels.json`** as `{"requirements":[{"text","type","weight"}...], "labels":{"r01":[1,1,1,1,0,1,1,1], ...}, "ranking":["r01",...]}`. **Stop and ask the user to check and correct the labels and ranking**; the gate depends on their judgment, not ours.
- [ ] **Step 7: Write `scripts/validate.py`.** It loads the real `JuliaDecider` and bge embedder, runs `review` on r01–r10 with the requirements from `labels.json` (id = list index), and prints: agreement % (P ≥ 0.5 vs label), top-5 overlap with `ranking`, seconds per resume, and a per-requirement agreement table.
- [ ] **Step 8: Run the gate:** `backend/.venv/Scripts/python scripts/validate.py`. **Pass** = agreement ≥ 70% and overlap ≥ 4/5. Also print the extracted text of one two-column resume. If its columns are interleaved, report that swapping `pdf_text.py` to Docling (same `extract_text` signature) is the first fix to try. **Report the numbers to the user either way.** On fail: stop. Adding `OllamaDecider` (same `p_met` signature, JSON verdict `met`/`partial`/`not_met` → 0.9/0.5/0.1) is a plan change the user must approve.
- [ ] **Step 9: Commit** `feat: add pipeline, samples and validation gate`

### Task 7: Store (SQLite)

**Files:** Create `backend/app/store.py` · Test `backend/tests/test_store.py`

**Interfaces:**
- Consumes: `ScoreResult`, `ReqResult`
- Produces: `class Store(db_path: str)`, opening a new `sqlite3` connection per method (thread-safe for the worker), with methods:
  `create_job(name, job_text) -> int` · `list_jobs() -> list[dict]` · `get_job(job_id) -> dict | None` (includes `requirements`) · `set_requirements(job_id, reqs: list[dict]) -> None` (replaces all rows, sets status `confirmed`) · `add_applicant(job_id, filename) -> int` · `get_applicant(applicant_id) -> dict | None` (includes `results` joined with requirement text/type) · `queued_ids() -> list[int]` · `save_result(applicant_id, sr: ScoreResult, results: list[ReqResult]) -> None` · `mark_failed(applicant_id, error: str) -> None` · `requeue_job(job_id) -> list[int]` · `status(job_id) -> dict` (`{"done", "total"}`) · `ranking(job_id) -> list[dict]` · `delete_job(job_id) -> None`

- [ ] **Step 1: Write failing tests** (use the `tmp_path` db)

```python
def test_job_roundtrip_and_confirm(): # create → status "draft"; set_requirements → "confirmed", requirements in position order
def test_ranking_order(): # scores 70/70/90, must_met 1/2/0, plus one queued and one failed → order 90, 70(must 2), 70(must 1), queued, failed
def test_ranking_tiebreak_filename(): # same score and must_met → filename asc
def test_status_counts_done_and_failed()
def test_save_result_replaces_previous_results(): # save twice with different ReqResults → get_applicant has only the 2nd set
def test_requeue_clears_scores_and_results(): # after requeue: status queued, score None, results []
def test_delete_job_cascades(): # requirements, applicants, results gone
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** the schema from spec §7 with `ON DELETE CASCADE` and `PRAGMA foreign_keys=ON` per connection. **Step 4: Run** → PASS. **Step 5: Commit** `feat: add sqlite store`

### Task 8: Worker

**Files:** Create `backend/app/worker.py` · Test `backend/tests/test_worker.py`

**Interfaces:**
- Consumes: `Store`, `extract_text`, `review`, `NoTextError`
- Produces: `class Worker(store: Store, uploads_dir: Path, decider: Decider, embed: Embed)` with `.start()` (daemon thread; first enqueues `store.queued_ids()`), `.enqueue(ids: list[int])`, `.join_idle(timeout: float)` (test helper: waits until the queue is empty), and `process(applicant_id)`

- [ ] **Step 1: Write failing tests** (fake decider and embed, real Store, sample PDFs written into `tmp_path`)

```python
def test_worker_scores_queued_applicant(): # status done, score set, results saved
def test_worker_marks_scanned_pdf_failed(): # error == "No text found — scanned PDF?"
def test_worker_marks_failed_and_continues(): # corrupt bytes for #1, valid for #2 → #1 failed with "Not a readable PDF", #2 done
def test_start_picks_up_queued_from_previous_run(): # applicant left queued in the db before start() → done afterwards
def test_process_reads_requirements_at_process_time(): # set_requirements between enqueue and processing → results use the new requirement ids
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** `process` reads `uploads_dir/{job_id}/{id}.pdf` and the job's current requirements. `NoTextError` → `mark_failed(id, "No text found — scanned PDF?")`; any other exception → `mark_failed(id, str(e))`. **Step 4: Run** → PASS. **Step 5: Commit** `feat: add background worker`

### Task 9: API, app wiring, run.py

**Files:** Create `backend/app/api.py`, `backend/app/main.py`, `run.py` · Test `backend/tests/test_api.py`

**Interfaces:**
- Consumes: everything above
- Produces: `@dataclass Deps(store: Store, uploads_dir: Path, extract: Callable[[str], list[dict]], worker: Worker)`; `create_app(deps: Deps, static_dir: Path | None = None) -> FastAPI`. Routes and JSON shapes as in spec §7. `POST /api/jobs` returns `{"job": job, "warning": str | None}`; `POST /resumes` returns `{"accepted":[{"id","filename"}], "rejected":[{"filename","reason"}]}`.

- [ ] **Step 1: Write failing tests** (`TestClient`, fake extract, worker with fake decider)

```python
def test_create_job_extracts_requirements(): # job status draft, requirements from fake extract with weights 2/1
def test_create_job_ollama_down(): # extract raises RequirementsUnavailable → 200, requirements [], warning == "Couldn't reach Ollama — start it, or type the requirements yourself."
def test_put_requirements_confirms(): # status confirmed
def test_put_empty_requirements_rejected(): # 400
def test_put_invalid_requirements_rejected(): # 422 for: text > 200 chars, 21 requirements, type "optional", weight <= 0
def test_upload_before_confirm_rejected(): # 409, detail "Confirm the requirements first"
def test_upload_mixed_files(): # 1 good pdf, 1 .txt, 1 11MB pdf → accepted 1, rejected 2 with the filename in each reason
def test_upload_over_100_files_rejected(): # 400
def test_upload_filename_is_only_a_label(): # filename "../../evil.pdf" → stored at uploads/{job}/{id}.pdf, applicant filename "../../evil.pdf", nothing written outside uploads_dir
def test_status_and_ranking_after_processing(): # worker.join_idle → status done==total, ranking sorted
def test_put_requirements_requeues_applicants(): # after scoring, PUT new reqs → applicants requeued, final results only reference new requirement ids
def test_applicant_detail(): # results with requirement text, type, probability, evidence
def test_export_csv(): # header: rank,filename,score,must_met,must_total,flagged,<req texts...>,error ; failed row last with empty score
def test_delete_job_removes_files(): # 204, uploads/{job_id} gone, GET job → 404
def test_spa_fallback(): # static_dir with index.html → GET /jobs/1/applicants/2 returns index.html; GET /api/nope → 404 JSON
```

- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement `api.py`.** PDF check = `is_pdf`; size check reads the bytes and compares to 10 × 1024 × 1024. Mount static files when `static_dir` exists, plus a catch-all `GET /{path:path}` (non-`api`) that returns `index.html`.
- [ ] **Step 4: Implement `main.py`.** Build the real deps: `Store("data/app.db")`, `uploads_dir = data/uploads`, `extract = req_extract.extract_requirements`, `JuliaDecider(MODEL_DIR)`, and an embed using `SentenceTransformer("BAAI/bge-small-en-v1.5").encode(..., normalize_embeddings=True)`. Start the worker and export `app = create_app(deps, static_dir=Path("frontend/dist"))`. All paths are resolved from the repo root. `run.py`: `uvicorn.run("app.main:app", app_dir="backend", port=8000)`.
- [ ] **Step 5: Run** the tests → PASS. Then smoke-test: `python run.py`, `curl -F name=Test -F file=@samples/job.pdf localhost:8000/api/jobs` returns requirements.
- [ ] **Step 6: Commit** `feat: add API and app wiring`

### Task 10: Frontend scaffold, API client, Jobs page

**Files:** Create `frontend/` (Vite react-ts), `frontend/src/api.ts`, `frontend/src/pages/JobsPage.tsx`; modify `frontend/vite.config.ts`, `frontend/src/main.tsx`

**Interfaces:**
- Consumes: the API from Task 9
- Produces: types `Job`, `Requirement {id?, text, type: "must"|"nice", weight}`, `RankRow`, `ApplicantDetail`, `Status`; functions `listJobs`, `getJob`, `createJob(name, file)`, `saveRequirements(jobId, reqs)`, `uploadResumes(jobId, files)`, `getStatus`, `getRanking`, `getApplicant`, `deleteJob`, `exportUrl(jobId)`. Each throws `Error(detail)` on a non-2xx response. Routes: `/` → JobsPage, `/jobs/:jobId` and `/jobs/:jobId/applicants/:applicantId` → JobPage.

- [ ] **Step 1: Scaffold.** `npm create vite@latest frontend -- --template react-ts`; `npm i react-router tailwindcss @tailwindcss/vite`. Add the Tailwind plugin and `server.proxy: {"/api": "http://localhost:8000"}`.
- [ ] **Step 1b: Design pass.** Run the `ui-ux-pro-max:ui-ux-pro-max` and `impeccable:impeccable` skills with `ref/DESIGN.md` and spec §5 as input. Turn the DESIGN.md tokens into a Tailwind `@theme` in `src/index.css` (colors, Inter font, radii, spacing), and settle the shared pieces: pill button (primary, secondary, outline), text input, card, MUST/NICE chip, probability bar, and the ✓/✗ success/error marks. Tasks 11–12 reuse these.
- [ ] **Step 2: Write `api.ts`** with the types matching the Task 9 JSON exactly.
- [ ] **Step 3: Build JobsPage:** a job list (name, status, created date, link) and a "New job" form (name + PDF). On create, navigate to `/jobs/:id` and show the `warning` if there is one.
- [ ] **Step 4: Verify** that `npm run build` passes with no type errors, then manually create a job against the running backend.
- [ ] **Step 5: Commit** `feat: scaffold frontend with jobs page`

### Task 11: Job page — requirements editor, upload, progress

**Files:** Create `frontend/src/pages/JobPage.tsx`, `frontend/src/components/RequirementsEditor.tsx`, `frontend/src/components/ResumeUpload.tsx`

**Interfaces:**
- Consumes: `api.ts`
- Produces: `<RequirementsEditor job onSaved />`, `<ResumeUpload jobId onUploaded />`; JobPage owns `status` and polls `getStatus` every 1 s while `done < total`.

- [ ] **Step 1: RequirementsEditor.** Rows have text (maxLength 200), must/nice select, weight number (≥ 1), delete; plus "Add requirement" and "Confirm". Changing a row's type also resets its weight to that type's default (2/1). Confirm is disabled when the list is empty. When the job is `confirmed` and has applicants, Confirm reads "Save & re-score". After confirming, the editor collapses to a summary with an "Edit" button.
- [ ] **Step 2: ResumeUpload.** A multi-file PDF input that is hidden until the job is confirmed. It lists rejected files with their reasons and shows a progress bar `done / total`.
- [ ] **Step 3: Verify** that `npm run build` passes, then manually: edit the requirements, upload `samples/*.pdf`, watch the progress bar reach the total, and see the rejected `.txt`.
- [ ] **Step 4: Commit** `feat: add requirements editor and resume upload`

### Task 12: Results — applicant list + review panel

**Files:** Create `frontend/src/components/ApplicantList.tsx`, `frontend/src/components/ApplicantReview.tsx`; modify `JobPage.tsx`

**Interfaces:**
- Consumes: `getRanking`, `getApplicant`, `exportUrl`, `deleteJob`
- Produces: `<ApplicantList rows selectedId onSelect />`, `<ApplicantReview applicantId />`

- [ ] **Step 1: ApplicantList** (left column, matching the spec §5 layout): rank, filename, score, and ⚠ when `flagged`. Queued rows show "…"; failed rows are greyed out at the bottom with their error and no rank. Clicking a row navigates to `/jobs/:jobId/applicants/:id`. With no `applicantId` in the URL, the top-ranked row is selected. The list refreshes while polling.
- [ ] **Step 2: ApplicantReview** (right column): header with filename and score, "Must-haves met x/y", then one row per requirement: MUST/NICE badge, text, a bar at width `P×100%`, the percentage, and ✓ if P ≥ 0.5 else ✗. Each row expands to show the evidence in a quote block.
- [ ] **Step 3: Header actions:** an "Export CSV" link to `exportUrl`, and "Delete job" behind a `confirm()` dialog, which navigates to `/` afterwards. Below Tailwind's `md` breakpoint the two columns stack.
- [ ] **Step 4: Verify** that `npm run build` passes, then manually click through every sample applicant; refresh on an applicant URL keeps the selection; check the layout at 375 px width.
- [ ] **Step 5: Commit** `feat: add results list and review panel`

### Task 13: Demo build, checklist, speed check

**Files:** Create `README.md` (the setup steps from spec §10 plus the demo checklist)

- [ ] **Step 1:** `npm run build` in `frontend/`, then `python run.py`. Open `localhost:8000` and confirm the React app loads and deep links work.
- [ ] **Step 2: Run the spec §9 demo checklist** end to end: create job → edit requirements → upload 10 resumes → watch progress → click through the list → expand evidence → export CSV → see the failed scanned PDF → delete job. Note any failures.
- [ ] **Step 3: Speed check:** copy r01–r10 five times (50 files), upload them, and time from upload until `done == total`. The target is about 5 minutes or less. If it's over, try `JuliaDecider(device="cuda")` and re-time. Report both numbers.
- [ ] **Step 4: Run** `pytest` (fast suite) and `pytest -m slow`, and report the results.
- [ ] **Step 5: Commit** `docs: add README and demo checklist`
