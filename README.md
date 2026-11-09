# Resume Reviewer

A local, free AI resume reviewer for HR. Upload a job-requirement PDF and a batch of resume PDFs; the app ranks applicants with a 0–100 score and shows, for every requirement, the probability that it is met and the resume passage behind it. It advises; HR decides.

Everything runs on your machine: no paid API, no cloud.

## How it works

1. **Requirements:** a local LLM (Ollama, `qwen2.5:3b`) reads the job PDF and lists must-have and nice-to-have requirements. You edit and confirm them before anything is scored.
2. **Evidence:** each resume is split into section-sized chunks. For every requirement, BM25 keyword search and `bge-small-en-v1.5` embeddings each rank the chunks, and Reciprocal Rank Fusion picks the top 3.
3. **Decision:** the LLM is asked whether those excerpts show the requirement is met. P(met) is the model's own probability of answering "yes" vs "no" (token logprobs).
4. **Score:** `round(100 × Σ weight × P(met) / Σ weight)`; must-haves weigh 2, nice-to-haves 1 by default. A must-have below 50% flags the applicant (⚠) but never hides them.

Design and decisions: [docs/superpowers/specs/2026-11-09-ai-resume-reviewer-design.md](docs/superpowers/specs/2026-11-09-ai-resume-reviewer-design.md).

## Setup (Windows, macOS or Linux)

Needs Python 3.11+, Node 20+ and [Ollama](https://ollama.com).

```bash
ollama pull qwen2.5:3b
```

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

(On macOS/Linux use `backend/.venv/bin/python`.)

```bash
cd frontend && npm install && npm run build
```

## Run

```bash
python run.py
```

Open http://127.0.0.1:8000. The embedding model (~130 MB) downloads on first start. Data lives in `data/` (SQLite plus uploaded PDFs); deleting a job deletes its files.

**Frontend development:** run `python run.py`, then `npm run dev` in `frontend/` (Vite proxies `/api` to port 8000).

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest
```

The fast suite needs no models. `-m slow` runs the tests that call the real Ollama model.

**Accuracy check:** `python scripts/validate.py` scores the 10 sample resumes in `samples/` and compares them with the hand labels in `samples/labels.json` (pass: ≥ 70% verdict agreement and ≥ 4/5 top-5 overlap). `python scripts/make_samples.py` rebuilds the sample PDFs from `samples/src/`.

## Measured on the dev laptop

i7-12700H, 16 GB RAM, RTX 2050 (4 GB):

- Requirement extraction: ~3 s per job PDF.
- Scoring: 51 resumes × 8 requirements in 48 s.
- Sample set: 89% verdict agreement with hand labels, 4/5 top-5 overlap.

## Limits

- English, text-based PDFs only. Scanned PDFs are listed as failed ("No text found — scanned PDF?"); there is no OCR.
- A 3B model misjudges some requirements: on the sample set it missed an Information Systems degree as "related to Computer Science", GCP/Azure as cloud platforms and Oracle SQL. Always check the evidence.
- Requirements spread over several jobs ("3+ years" summed across roles) may not appear in any single excerpt.
- The accuracy numbers come from 10 fictional resumes, and the decider prompt was tuned on similar cases. Expect lower agreement on real resumes.
