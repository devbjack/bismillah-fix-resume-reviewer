# PRD: AI Resume Reviewer

- **Date:** 2026-11-09
- **Status:** Draft for review
- **Type:** Course project (requirement: "AI-powered resume reviewer"; no required stack)

## 1. Problem

HRD staff receive many resumes for one opening and have to decide who gets an interview. Reading every resume against the job requirements by hand is slow and inconsistent. HRD needs a ranked shortlist with a score and the evidence behind each score.

## 2. User

One HRD staff member, using the app on their own laptop. No accounts, no other users, no cloud.

## 3. Goals and success criteria

The app advises; HRD decides. It never rejects or contacts applicants.

| Goal | Measure |
|---|---|
| Fast enough to use | 50 resumes scored in ≤ about 5 minutes on the target laptop |
| Ranks sensibly | On the 10-resume sample set, ≥ 4 of the app's top 5 are in HRD's hand-ranked top 5 |
| Trustworthy | Every score breaks down into per-requirement probabilities, each with an evidence passage |
| Free and local | No paid API; runs offline once models are downloaded |

**Target laptop:** i7-12700H (14 cores), 16 GB RAM, RTX 2050 (4 GB VRAM), Windows 11, Python 3.11, Node 24.

## 4. Scope

### In scope (v1)
- Create a job from a job-requirement PDF; the LLM extracts the requirements.
- HRD edits the requirements (text, must/nice, weight, add, delete) and confirms them.
- Upload up to 100 resume PDFs per upload; more can be added later.
- Background scoring with a progress bar.
- Results view: ranked applicants on the left; the selected applicant's review on the right.
- CSV export of the ranking.
- Jobs and results kept between sessions; delete a job and all of its files.

### Out of scope (v1)
- Logins, multiple users, cloud hosting
- Scanned/image PDFs (no OCR), DOCX, non-English resumes
- Auto-rejecting or emailing applicants; ATS/HR-system integration
- Extracting names, photos or personal details (the applicant label is the file name)

## 5. User flow

1. **Jobs page:** list of jobs; "New job" asks for a name and a job-requirement PDF.
2. **Requirements editor:** shows the extracted requirements. Each has text (≤ 200 chars), type `must`/`nice` and a weight (default must = 2, nice = 1). HRD edits, then clicks **Confirm**. Resumes cannot be uploaded until requirements are confirmed.
3. **Upload resumes:** multi-file PDF upload, then a progress bar (`done / total`).
4. **Results:** a two-panel layout.
5. **Export CSV** or **Delete job** at any time.

### Results layout

```
┌─ Backend Developer ─────────────────────────────── [Export CSV] ┐
│ APPLICANTS (32)       │  #1  andi_pratama.pdf          Score 86  │
│ ───────────────────── │  Must-haves met 5/5                      │
│▶ 1  andi_pratama   86 │ ──────────────────────────────────────── │
│  2  budi_s.pdf     81 │  MUST  Python 3+ years       ████████░ 87% ✓│
│  3  citra_w.pdf    77 │        ▸ "Backend Engineer, 2020–2024 ·   │
│  4  dewi_l.pdf  ⚠  74 │           built REST APIs in Python..."   │
│  5  eka_r.pdf      70 │  MUST  SQL databases         ███████░░ 78% ✓│
│  …                    │  NICE  Docker                ███░░░░░░ 31% ✗│
└───────────────────────┴──────────────────────────────────────────┘
```

- **Left list:** rank, file name, score, and ⚠ if any must-have has P(met) < 0.5. Failed applicants appear greyed out at the bottom with their error and no score. The top applicant is selected by default.
- **Right panel:** score, must-haves met (`x / y`), then one row per requirement: type, text, P(met) as a bar and a percentage, ✓ if P ≥ 0.5 else ✗. Each row expands to show its evidence passage.
- **URL:** `/jobs/:id/applicants/:applicantId`, so refreshing keeps the selection.
- **Narrow screens:** the panels stack, list above review.

## 6. Approach and why

### Decision record

| Option | Verdict | Reason |
|---|---|---|
| Ask an LLM to score each resume 0–100 | Rejected | Small local models give unstable numbers that aren't comparable across resumes and are hard to explain |
| Jev (TypeSafe AI decision model) | Rejected | Paid API |
| Ollama 3B with typed JSON verdicts per requirement | Fallback | Works and explains, but ~10–20 s per resume and no probabilities |
| RRF over whole resumes as the final ranking | Rejected | Gives only relative ranks, not a meaningful 0–100 score; rewards keyword stuffing |
| **Julia 1 per requirement, with RRF retrieval of evidence** | **Chosen** | Free (Apache 2.0), runs on CPU, returns typed probabilities like Jev; RRF keeps Julia's input short and provides evidence |

### Pipeline

1. **Job PDF → requirements (once per job):** Ollama (`qwen2.5:3b`) with a JSON-schema output: `{"requirements": [{"text": string ≤200, "type": "must" | "nice"}]}`, at most 20 items. HRD reviews before use.
2. **Resume PDF → text:** PyMuPDF.
3. **Text → chunks:** split at blank lines and heading-like lines, then merge neighbors up to ~1,000 characters; hard-split anything over 1,500 characters.
4. **Requirement + chunks → top 3 chunks:**
   - BM25 rank (`rank_bm25`, lowercase word tokens)
   - Embedding rank (`BAAI/bge-small-en-v1.5`, cosine similarity)
   - RRF: `score(c) = 1/(60 + rank_bm25(c)) + 1/(60 + rank_emb(c))`; keep the 3 highest.
5. **Julia decision:** a `noul` question with `state` = the top 3 chunks joined, `instructions` = `Does the candidate meet this requirement: <text>?`, criteria `false` = "The text does not show the candidate meets this requirement", `true` = "The text shows the candidate meets this requirement". Output: P(true) = P(met). Evidence = the top-ranked chunk.
6. **Score:** `score = round(100 × Σ(weight × P(met)) / Σ(weight))`. `must_met` = must-haves with P ≥ 0.5. `flagged` = any must-have with P < 0.5. Ties are broken by `must_met`, then by file name.

## 7. Architecture

```
React app (Vite) ──JSON──► FastAPI API ──► SQLite (data/app.db)
  frontend/                  backend/
                               ├─ Ollama (qwen2.5:3b, GPU)
                               ├─ bge-small-en-v1.5 (CPU)
                               └─ Julia 1 (CPU)
```

- **Frontend:** Vite + React + TypeScript, Tailwind, React Router, plain `fetch`. Polls `/status` every second while scoring.
- **Backend:** FastAPI. Models load once at startup.
- **Dev:** `npm run dev` in `frontend/` (proxies `/api`) and `uvicorn` in `backend/`.
- **Demo:** `npm run build`; FastAPI serves `frontend/dist`, so `python run.py` starts everything on one port.

### Backend modules

| Module | Input → Output |
|---|---|
| `pdf_text` | PDF bytes → text (empty string if none) |
| `requirements` | job text → list of `{text, type}` via Ollama |
| `chunker` | text → list of chunk strings |
| `retriever` | requirement + chunks → top 3 chunks (BM25 + embeddings + RRF) |
| `decider` | requirement + chunks → P(met). Julia implementation; replaceable by an Ollama implementation with the same signature |
| `scorer` | `[(type, weight, P)]` → score, must_met, must_total, flagged |
| `store` | SQLite access for all tables |
| `worker` | background thread that processes queued applicants one at a time |
| `api` | HTTP routes calling the modules above |

### API

| Method & path | Purpose |
|---|---|
| `POST /api/jobs` | multipart: name + PDF → job with extracted requirements (status `draft`) |
| `GET /api/jobs` | list jobs |
| `GET /api/jobs/{id}` | job with its requirements |
| `PUT /api/jobs/{id}/requirements` | replace the requirements and confirm (status `confirmed`); re-scores existing applicants |
| `POST /api/jobs/{id}/resumes` | multipart, many PDFs → applicants queued; returns accepted and rejected files |
| `GET /api/jobs/{id}/status` | `{done, total}` where done counts `done` + `failed` |
| `GET /api/jobs/{id}/ranking` | applicants sorted by score; failed ones last |
| `GET /api/applicants/{id}` | applicant with per-requirement probability and evidence |
| `GET /api/jobs/{id}/export.csv` | rank, file name, score, must_met/must_total, flagged, one P column per requirement; failed applicants last with blank score and their error |
| `DELETE /api/jobs/{id}` | delete the job, its rows and its uploaded files |

### Data (SQLite)

| Table | Fields |
|---|---|
| `jobs` | id, name, job_text, status (`draft`/`confirmed`), created_at |
| `requirements` | id, job_id, text, type (`must`/`nice`), weight, position |
| `applicants` | id, job_id, filename, status (`queued`/`done`/`failed`), error, score, must_met, must_total, flagged |
| `results` | applicant_id, requirement_id, probability, evidence |

Uploaded files are saved in `data/uploads/{job_id}/`.

## 8. Error handling

| Situation | Behavior |
|---|---|
| Resume has no extractable text | Applicant `failed`, error "No text found — scanned PDF?" |
| Not a PDF, corrupt, or > 10 MB | Rejected at upload with the file named; other files continue |
| More than 100 files in one upload | Request rejected with a message |
| Resume upload while requirements are still `draft` | Rejected with "Confirm the requirements first" |
| Ollama unreachable on job creation | Job created with an empty editor and the message "Couldn't reach Ollama — start it, or type the requirements yourself." |
| LLM returns no requirements | Empty editor; HRD types them |
| Crash or restart mid-scoring | On startup, `queued` applicants are processed again |
| Requirements edited after scoring | All applicants of the job are re-queued and re-scored |
| Unexpected error on one resume | That applicant is `failed` with the error message; the worker continues |

## 9. Testing and validation

### Step 0: Julia validation (before building UI)
- **Sample set** in `samples/`: 1 job PDF and 10 resumes of fictional people (strong, medium and weak fits), plus 1 scanned PDF.
- **Hand labels** in `samples/labels.json`: met/not met per requirement × resume, plus HRD's own ranking.
- **`scripts/validate.py`** reports verdict agreement (P ≥ 0.5 vs label) and top-5 overlap.
- **Pass:** ≥ 70% agreement and ≥ 4 / 5 overlap. **Fail:** switch `decider` to the Ollama implementation and re-run.

### Automated (pytest)
| Level | Covers | Real models |
|---|---|---|
| Unit | chunker, RRF fusion, scorer, store | No |
| Pipeline | sample PDFs → ranking, with fake decider and fake LLM | No |
| API | create, edit, upload (incl. bad file), status, ranking, CSV, delete | No |
| Smoke (`slow`) | full pipeline on 2 resumes | Yes |

### Manual
- **Demo checklist:** create job → edit requirements → upload 10 resumes → watch progress → click through the list → expand evidence → export CSV → see the failed scanned PDF → delete job.
- **Speed check:** 50 resumes (samples × 5) in ≤ about 5 minutes.

## 10. Setup

1. Install Ollama, then `ollama pull qwen2.5:3b`.
2. `pip install -r backend/requirements.txt` (Julia is installed from its Hugging Face repo as described in its model card).
3. `npm install` and `npm run build` in `frontend/`.
4. `python run.py`. Julia (~550 MB) and bge-small (~130 MB) download on first run.

## 11. Risks and limitations

| Risk | Mitigation |
|---|---|
| Julia 1 is a first release, unvalidated on resumes | Step 0 validation with a pass/fail threshold; swappable `decider` |
| Requirements summed across a resume ("3+ years" over several jobs) may not appear in any single chunk | Documented limitation; measured in Step 0 |
| Julia is weak at arithmetic and world knowledge (its model card says so) | Same as above; HRD sees evidence and makes the final call |
| Speed estimates are not measured yet | Speed check; Julia can use `device="cuda"` if CPU is too slow |
| A wrong requirement list makes every score wrong | HRD must confirm requirements before scoring |
| Bias | Scoring only asks about the listed requirements; name, age, gender and photos are never a criterion. HRD decides |
