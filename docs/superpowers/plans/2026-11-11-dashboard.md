# Job Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the job page into a dashboard: a fixed, independently scrolling applicant list on the left with "Overview" pinned on top, an Overview page with five summary panels, and Setup moved to its own view.

**Architecture:** One new backend method `Store.summary` computes every number, and `GET /api/jobs/{id}/summary` exposes it. On the frontend, `JobPage` becomes a shell (left list, job header, view switch by URL). `Overview` fetches the summary and renders tiles plus three hand-written SVG charts from `charts.tsx`. `SetupView` holds the existing editor and upload.

**Tech Stack:** Python 3.11, FastAPI, sqlite3, pytest · React 19, react-router 8, Tailwind v4, lucide-react. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-11-dashboard-design.md`

## Global Constraints

- Qualified = scored (`status = 'done'`) and `must_met == must_total`. Met = probability ≥ 0.5.
- Qualified % = `round(100 × qualified / scored)`, shown as "–" when `scored == 0`. Average and coverage % are rounded to whole numbers in the UI.
- Histogram band = `min(score // 10, 9)`; labels "0–9" … "80–89", last band "90–100".
- Coverage order: must-haves first, then editor `position`.
- `best` and `top` follow `Store.ranking` order; `top` holds at most 5 qualified applicants.
- No new npm or pip dependencies; charts are plain SVG/CSS.
- Design tokens from `ref/DESIGN.md` via `src/index.css` (`aubergine`, `aubergine-mute`, `cream`, `lavender`, `hairline`, `success`, `error`, `ink`, `ink-mute`). All UI text ≥ 11 px, visible focus, no new animation beyond 150 ms hover transitions.
- Left list 300 px wide on ≥ 768 px; below 768 px stacked with `max-h-[40vh]` and its own scroll; no horizontal scroll at 375 px.
- User-facing copy is verbatim from spec §5: "Upload resumes in Setup to see the summary." and "No one meets every must-have yet. Applicants marked ⚠ in the list are the closest."

## Review Focus

1. **Requirements re-saved while on Overview:** every applicant is requeued, so the scored count drops and then climbs again. The charts must refetch and never show stale numbers. → Task 4 browser step "re-save requirements while on Overview".
2. **Applicants with very long file names and 200-character requirements:** these truncate or wrap inside their panels and never push the page wider than 375 px. → Task 4 browser step at 375 px with a 200-char requirement.
3. **0% and 100% qualified, and a job with only failed resumes:** the donut draws an empty or full ring without artefacts, and the tiles show "–" instead of NaN. → Task 2 (charts) handles zero totals, and Task 4 checks it in the browser with an all-scanned upload.
4. **Unknown or foreign applicant URL before the ranking has loaded:** no redirect fires until the ranking is loaded, so a valid deep link is never bounced to Overview. → Task 3 browser step "refresh on a deep link".
5. **Ties in score:** the top 5 and the left list show the same order. → Task 1 test `test_summary_top_is_qualified_only_in_rank_order` includes a tie.

---

## File Structure

```
backend/app/store.py                 + Store.summary(job_id) -> dict
backend/app/api.py                   + GET /api/jobs/{job_id}/summary
backend/tests/test_store.py          + summary tests
backend/tests/test_api.py            + endpoint test
frontend/src/api.ts                  + Summary type, getSummary
frontend/src/components/charts.tsx   new: Donut, Histogram, CoverageBars
frontend/src/components/Overview.tsx new: summary panels and states
frontend/src/components/SetupView.tsx new: RequirementsEditor + ResumeUpload + warning
frontend/src/components/ApplicantList.tsx   pinned Overview item, own scroll
frontend/src/pages/JobPage.tsx       shell: list, header, view switch
frontend/src/main.tsx                + /jobs/:jobId/setup route
```

---

### Task 1: `Store.summary` and the summary endpoint

**Files:** Modify `backend/app/store.py`, `backend/app/api.py` · Test `backend/tests/test_store.py`, `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `Store.ranking(job_id)` (existing; done rows first, ordered by score desc, must_met desc, filename asc)
- Produces: `Store.summary(job_id: int) -> dict` with keys `total, scored, queued, failed, qualified` (int), `average_score` (float, 1 decimal, or None), `best` (`{id, filename, score}` or None), `histogram` (list of 10 ints), `coverage` (list of `{requirement_id, text, type, met, scored}`), `top` (list of `{id, filename, score, must_met, must_total}`). `GET /api/jobs/{job_id}/summary` returns that dict, or 404 `"Job not found"`.

- [ ] **Step 1: Write failing store tests.** Add a helper to `test_store.py` that saves an applicant with given probabilities and derives `must_met` from the job's requirement types:

```python
def scored(store, job, name, score, probs):
    reqs = store.get_job(job)["requirements"]
    a = store.add_applicant(job, name)
    musts = [p for r, p in zip(reqs, probs) if r["type"] == "must"]
    met = sum(p >= 0.5 for p in musts)
    store.save_result(a, ScoreResult(score, met, len(musts), met < len(musts)),
                      [ReqResult(r["id"], p, "ev") for r, p in zip(reqs, probs)])
    return a

FOUR = [{"text": f"M{i}", "type": "must", "weight": 2} for i in range(2)] + [{"text": "N1", "type": "nice", "weight": 1}]

def test_summary_empty_job(store):  # job with FOUR confirmed, no applicants
    s = store.summary(job)
    assert (s["total"], s["scored"], s["queued"], s["failed"], s["qualified"]) == (0, 0, 0, 0, 0)
    assert s["average_score"] is None and s["best"] is None and s["top"] == []
    assert s["histogram"] == [0] * 10
    assert [(c["text"], c["met"], c["scored"]) for c in s["coverage"]] == [("M0", 0, 0), ("M1", 0, 0), ("N1", 0, 0)]

def test_summary_counts_by_status(store):  # 2 scored, 1 queued (add_applicant only), 1 mark_failed
    assert (s["total"], s["scored"], s["queued"], s["failed"]) == (4, 2, 1, 1)

def test_summary_qualified_needs_every_must(store):
    # a: [0.5, 0.9, 0.1] -> qualified (0.5 counts); b: [0.9, 0.49, 0.9] -> not
    assert s["qualified"] == 1

def test_summary_no_musts_all_scored_qualify(store):  # requirements: only N1
    assert s["qualified"] == s["scored"] == 2

def test_summary_histogram_band_edges(store):  # scores 0, 9, 10, 99, 100
    assert s["histogram"] == [2, 1, 0, 0, 0, 0, 0, 0, 0, 2]

def test_summary_coverage_counts_and_order(store):
    # requirements saved in order N1, M0 (nice first in the editor); 3 scored applicants with
    # N1 probs 0.9, 0.9, 0.1 and M0 probs 0.2, 0.6, 0.7; one queued applicant is ignored
    assert [(c["text"], c["type"], c["met"], c["scored"]) for c in s["coverage"]] == [("M0", "must", 2, 3), ("N1", "nice", 2, 3)]

def test_summary_top_is_qualified_only_in_rank_order(store):
    # 7 qualified (scores 90, 80, 80, 70, 60, 50, 40; the two 80s named "b.pdf" and "a.pdf") + 1 unqualified scoring 95
    assert [t["filename"] for t in s["top"]] == ["q90.pdf", "a.pdf", "b.pdf", "q70.pdf", "q60.pdf"]
    assert s["top"][0]["must_met"] == s["top"][0]["must_total"] == 2

def test_summary_best_and_average(store):  # best_id = scored(..., "best.pdf", 95, unqualified probs); scored 60; one failed
    assert s["best"] == {"id": best_id, "filename": "best.pdf", "score": 95}
    assert s["average_score"] == 77.5
```

- [ ] **Step 2: Run** `cd backend && .venv/Scripts/python -m pytest tests/test_store.py -q -k summary` → FAIL (`AttributeError: 'Store' object has no attribute 'summary'`).
- [ ] **Step 3: Implement `Store.summary`.**
  - Counts and `qualified` come from one aggregate query over `applicants`.
  - `average_score` is `round(AVG(score), 1)` over done rows.
  - `histogram` is filled in Python from the done rows' scores.
  - `coverage` uses `requirements LEFT JOIN results LEFT JOIN applicants` with `SUM(r.probability >= 0.5 AND a.status = 'done')`, grouped per requirement and ordered `(q.type = 'must') DESC, q.position`.
  - `best` and `top` filter `self.ranking(job_id)`: done rows, then done rows with `must_met == must_total`, taking 5.
- [ ] **Step 4: Run** the same command → PASS. Then add the endpoint test to `test_api.py`:

```python
def test_summary_endpoint(env):  # make_job + confirm + upload "a.pdf" with pdf_with("Python"), join_idle
    s = client.get(f"/api/jobs/{job['id']}/summary").json()
    assert set(s) == {"total", "scored", "queued", "failed", "qualified", "average_score", "best", "histogram", "coverage", "top"}
    assert s["scored"] == 1 and s["qualified"] == 1 and s["best"]["filename"] == "a.pdf"
    assert client.get("/api/jobs/999/summary").status_code == 404
```

- [ ] **Step 5: Run** → FAIL (404 for the existing job). Add the route `GET /api/jobs/{job_id}/summary` next to `ranking` in `create_app`, using `job_or_404`. Run → PASS. Then run the full suite: `.venv/Scripts/python -m pytest -q` → all pass (87 existing + 9 new).
- [ ] **Step 6: Commit** `feat: add job summary endpoint`

### Task 2: Summary client and SVG charts

**Files:** Modify `frontend/src/api.ts` · Create `frontend/src/components/charts.tsx`

**Interfaces:**
- Consumes: the Task 1 JSON shape.
- Produces:
  - `api.ts`: `interface Summary` mirroring Task 1 exactly (`average_score: number | null`, `best: {id; filename; score} | null`, `coverage: {requirement_id; text; type: ReqType; met; scored}[]`, `top: {id; filename; score; must_met; must_total}[]`) and `getSummary(jobId: number): Promise<Summary>`.
  - `charts.tsx`:
    - `Donut({ qualified, notQualified, failed }: { qualified: number; notQualified: number; failed: number })`
    - `Histogram({ bins }: { bins: number[] })`
    - `CoverageBars({ rows }: { rows: Summary['coverage'] })`

- [ ] **Step 1: Add the `Summary` type and `getSummary`** (`request<Summary>(\`/api/jobs/${jobId}/summary\`)`).
- [ ] **Step 2: Write `Donut`.**
  - SVG `viewBox="0 0 120 120"`, ring radius 48, stroke 14, on a `hairline` track.
  - Slices in order: qualified `success`, not qualified `aubergine-mute`, failed `error`, drawn with `stroke-dasharray`/`stroke-dashoffset` starting at 12 o'clock. A slice with count 0 draws nothing.
  - Centre text: `round(100 × qualified / (qualified + notQualified))` + "%", or "–" when that denominator is 0.
  - `role="img"` with `aria-label` "{pct}% qualified: {qualified} of {qualified+notQualified} scored, {failed} could not be scored".
  - A legend beside it with a coloured square, label and count for each of the three slices.
- [ ] **Step 3: Write `Histogram`.**
  - Ten bars in a flex row (`items-end`), each with height `count / max(...bins, 1) × 100%` of a 160 px plot area.
  - Count-0 bars render a 2 px `hairline` stub. Other bars are `aubergine` with rounded tops.
  - Each bar has `title="{a}–{b}: {n} applicant(s)"` (last band "90–100").
  - Axis labels "0 20 40 60 80 100" below, in `text-[11px] text-ink-mute tabular-nums`.
  - `role="img"` with an `aria-label` that lists the non-empty bands.
- [ ] **Step 4: Write `CoverageBars`.** One row per entry: `TypeChip`, the text (wraps; `min-w-0`), a 8 px `hairline` track with an `aubergine` fill at `met / scored`, and "{met} of {scored} · {pct}%". When `scored == 0`, show "–" and an empty track.
- [ ] **Step 5: Verify** `cd frontend && npm run build` → `✓ built`, no type errors.
- [ ] **Step 6: Commit** `feat: add summary client and SVG charts`

### Task 3: Dashboard shell: fixed list, job header, views

**Files:** Create `frontend/src/components/SetupView.tsx`, `frontend/src/components/Overview.tsx` · Modify `frontend/src/pages/JobPage.tsx`, `frontend/src/components/ApplicantList.tsx`, `frontend/src/main.tsx`

**Interfaces:**
- Consumes: `getSummary`, `Donut`, `Histogram`, `CoverageBars` (Task 2); existing `RequirementsEditor({ job, hasApplicants, onSaved })`, `ResumeUpload({ jobId, status, onUploaded })`, `ApplicantReview({ applicantId, version })`.
- Produces:
  - `ApplicantList({ jobId, rows, selectedId, overviewSelected }: { ...; overviewSelected: boolean })`
  - `SetupView({ job, status, onSaved, onUploaded, warning }: { job: Job; status: Status; onSaved: (job: Job) => void; onUploaded: () => void; warning?: string | null })`
  - `Overview({ jobId, version }: { jobId: number; version: string })`
  - Route `/jobs/:jobId/setup` → `JobPage`.

- [ ] **Step 1: Add the route** `/jobs/:jobId/setup` to `main.tsx`.
- [ ] **Step 2: `SetupView`.** Move from `JobPage`:
  - the Ollama/scanned `warning` notice (shown while the job is draft)
  - `RequirementsEditor`, keeping its existing `key`
  - `ResumeUpload`, shown when confirmed
  - the "Upload resumes above…" empty note

  Behaviour stays the same; `hasApplicants` = `status.total > 0`.
- [ ] **Step 3: `ApplicantList`.**
  - The `nav` becomes `flex h-full min-h-0 flex-col`.
  - Above the existing heading, add a pinned link "Overview" (lucide `LayoutDashboard` icon) to `/jobs/:jobId`, with the same selected style as applicant rows when `overviewSelected`.
  - The `<ol>` gets `min-h-0 flex-1 overflow-y-auto`, so only the rows scroll.
- [ ] **Step 4: `Overview`.**
  - Fetch `getSummary(jobId)` in an effect keyed on `[jobId, version]`, ignoring late responses like `ApplicantReview` does.
  - Render the spec §5 grid:
    - Tiles: `grid-cols-2 lg:grid-cols-5`.
    - Donut + Histogram: `lg:grid-cols-3`, histogram `lg:col-span-2`.
    - Coverage + Top 5: `lg:grid-cols-2`.
  - Tiles:
    - Applicants: `total` / "{scored} scored"
    - Qualified: pct or "–" / "{qualified} of {scored}"
    - Best score: `best.score` / file name as a link to the review
    - Average: rounded / "of {scored} scored"
    - Failed: `failed` / "couldn't be read"
  - Top 5 rows link to `/jobs/:jobId/applicants/:id`.
  - States:
    - Loading skeleton.
    - `total == 0`: the verbatim copy plus a `buttonClass('primary')` link to Setup.
    - Empty `top`: the verbatim copy.
- [ ] **Step 5: `JobPage` shell.**
  - Keep the data loading, polling, `syncError`/`deleteError` and delete.
  - Add `rowsLoaded` (true after the first successful ranking fetch).
  - View:
    - `params.applicantId` → `'applicant'`
    - pathname ends with `/setup` → `'setup'`
    - otherwise `'overview'`
  - Redirects with `<Navigate replace>`:
    - draft job on overview → `/jobs/:id/setup`
    - `rowsLoaded` and the applicant isn't in `rows` → `/jobs/:id`
  - Layout:
    - `md:grid md:grid-cols-[300px_minmax(0,1fr)] md:h-[calc(100dvh-3.5rem)]`
    - Left column: `bg-cream border-r border-hairline max-h-[40vh] md:max-h-none overflow-hidden` holding `ApplicantList`.
    - Right column: `min-w-0 overflow-y-auto`, with the job header, then the notices, then the view.
  - Job header:
    - "All jobs" link and the job name.
    - While `scoring`, a slim progress bar (h-1.5, `role="progressbar"`) with "{done} of {total} scored".
    - Buttons: Setup (`buttonClass('secondary','sm')`), Export CSV, Delete job.
  - Pass `version={`${status.done}/${status.total}`}` to `Overview`.
- [ ] **Step 6: Verify** `npm run build` passes. Then with `python run.py` and a job of 10 sample resumes, check in the browser:
  - Overview is selected by default.
  - Clicking a row shows the review, and Overview returns.
  - `/setup` shows the editor.
  - A new draft job opens on Setup.
  - **Refreshing on a deep link** `/jobs/:id/applicants/:id` keeps that applicant (Review Focus 4).
  - `/jobs/:id/applicants/99999` falls back to Overview.
- [ ] **Step 7: Commit** `feat: dashboard shell with fixed applicant list and views`

### Task 4: Verify the dashboard end to end and polish

**Files:** fixes only, in the files above.

- [ ] **Step 1: 51-resume run.** Upload the 51 sample copies, then check:
  - The left list scrolls on its own while the main area stays put, and vice versa.
  - Every Overview number equals `GET /api/jobs/:id/summary` (compare with curl).
  - The histogram tooltip appears on hover.
  - The Best tile and Top 5 rows open the right review.
  - The charts update while scoring.
- [ ] **Step 2: Re-save requirements while on Overview** (Review Focus 1): the numbers drop to the requeued state and refill; nothing stale remains after scoring finishes.
- [ ] **Step 3: Edge data** (Review Focus 3):
  - A job with only `r11_scanned.pdf`: the donut is all "could not score", Qualified and Average show "–", and Top 5 shows the verbatim empty copy.
  - A job where everyone qualifies (only `r01.pdf`): a full green ring.
- [ ] **Step 4: 375 px** (Review Focus 2): with a 200-character requirement and a long file name, the list stacks with its own scroll, the panels wrap, and `document.documentElement.scrollWidth === 375`.
- [ ] **Step 5: Design check.** Run `impeccable detect --json` on `frontend/src/components/{Overview,charts,SetupView,ApplicantList}.tsx` and `frontend/src/pages/JobPage.tsx`. Fix real findings; disclose any ignore with its reason.
- [ ] **Step 6: Run** `cd backend && .venv/Scripts/python -m pytest -q -m "slow or not slow"` → all pass. Run `cd frontend && npm run build` → built.
- [ ] **Step 7: Commit** `fix: dashboard polish from end-to-end checks` (only if Steps 1–5 changed code).
