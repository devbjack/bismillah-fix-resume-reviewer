# Spec: Job dashboard

- **Date:** 2026-11-11
- **Status:** Draft for review
- **Builds on:** `docs/superpowers/specs/2026-11-09-ai-resume-reviewer-design.md` (the app as shipped on `master`, commit 31802fa)

## 1. Goal

Turn the job page into a visual dashboard. HR opens a job and sees within seconds how strong the applicant pool is and who to look at first, then clicks through applicants in a list fixed to the left edge without losing the overview.

## 2. Decisions

| Topic | Decision |
|---|---|
| Qualified | Every must-have met (P ≥ 0.5 on each). Same rule as the ⚠ flag. A job with no must-haves: every scored applicant qualifies. |
| Layout | "Overview" pinned at the top of a full-height left list; the main area shows Overview, an applicant review, or Setup. |
| Panels | Headline numbers, qualified donut, score histogram, requirement coverage, top 5 qualified. |
| Data | One backend endpoint computes every number (testable in pytest). |
| Charts | Hand-written SVG/CSS React components; no chart library. |

Out of scope: a summary across all jobs, adjustable qualified cut-offs, the "must-haves met breakdown" panel, chart animations, new dependencies.

## 3. Layout and navigation

```
┌───────────────── aubergine app bar (as today) ─────────────────┐
├──────────────┬─────────────────────────────────────────────────┤
│ ▦ Overview   │ Backend Developer   ▓▓▓▓░░ 12/50   ⚙Setup ⤓CSV 🗑│  job header
│──────────────│─────────────────────────────────────────────────│
│ 1 r01   95   │                                                 │
│ 2 r04 ⚠ 67   │   Overview  /  applicant review  /  Setup       │
│ …  (scrolls) │   (scrolls on its own)                          │
│ r11 ✕ failed │                                                 │
└──────────────┴─────────────────────────────────────────────────┘
```

- **Left list:** 300 px wide, fixed to the left edge, from below the app bar to the bottom of the window (`100dvh` minus the app bar), cream background, `overflow-y: auto`. "Overview" is pinned above the scrolling rows. The current item (Overview or an applicant) has the existing selected style.
- **Job header:** job name; a slim progress bar with "N of M scored", shown only while scoring; Setup (secondary pill), Export CSV, Delete job. Error notices (lost contact, delete failed, Ollama warning) sit directly under it.
- **Main area:** its own scroll container.

| URL | Main area |
|---|---|
| `/jobs/:id` | Overview |
| `/jobs/:id/applicants/:applicantId` | applicant review (existing `ApplicantReview`) |
| `/jobs/:id/setup` | requirements editor + resume upload (existing components, moved) |

- A **draft** job (requirements not confirmed) visiting `/jobs/:id` is redirected (replace) to `/jobs/:id/setup`.
- After confirming requirements or uploading, the user stays on Setup.
- An applicant id that is not in this job falls back to Overview (replace navigation).
- The Jobs list page is unchanged.
- **Below 768 px:** the list stacks above the main area with `max-height: 40vh` and its own scroll; the page scrolls normally; no horizontal scroll at 375 px.

## 4. Summary endpoint

`GET /api/jobs/{id}/summary` → 404 `{"detail": "Job not found"}` for an unknown job, otherwise:

```json
{
  "total": 51, "scored": 50, "queued": 0, "failed": 1,
  "qualified": 11,
  "average_score": 58.4,
  "best": {"id": 1, "filename": "r01.pdf", "score": 95},
  "histogram": [3, 1, 2, 4, 5, 7, 9, 5, 2, 12],
  "coverage": [{"requirement_id": 7, "text": "3+ years of Python", "type": "must", "met": 18, "scored": 50}],
  "top": [{"id": 1, "filename": "r01.pdf", "score": 95, "must_met": 4, "must_total": 4}]
}
```

Definitions (all over the job's applicants; "scored" = status `done`):

- `total`, `scored`, `queued`, `failed`: counts by status.
- `qualified`: scored applicants with `must_met == must_total` (this also covers jobs with no must-haves: 0 == 0).
- Qualified % shown in the UI = `round(100 × qualified / scored)`; shown as "–" when `scored == 0`. The UI also rounds `average_score` and coverage % to whole numbers.
- `average_score`: mean score of scored applicants, rounded to 1 decimal; `null` if none.
- `best`: first row of `Store.ranking(job_id)` with status `done`; `null` if none.
- `histogram`: 10 counts of scored applicants; band = `min(score // 10, 9)`, so 100 falls in the last band.
- `coverage`: one entry per requirement, `type = must` first, then editor position; `met` = scored applicants whose result for that requirement has probability ≥ 0.5; `scored` repeats the scored count for convenience.
- `top`: up to 5 qualified applicants in `Store.ranking` order.

Implementation: `Store.summary(job_id) -> dict` in `backend/app/store.py` (SQL aggregates plus the existing `ranking` order); the route in `backend/app/api.py` only checks the job exists and returns it.

## 5. Overview dashboard

```
┌ Applicants ┬ Qualified ┬ Best score ┬ Average ┬ Failed ┐   tiles
├────────────┴──────┬────┴────────────┴─────────┴────────┤
│ Qualified (donut) │ Score distribution (histogram)     │   1/3 + 2/3
├───────────────────┴──────┬─────────────────────────────┤
│ Requirement coverage     │ Top 5 qualified             │   1/2 + 1/2
└──────────────────────────┴─────────────────────────────┘
```

Below 1024 px main-area width the rows stack to one column and the tiles wrap two per row.

| Panel | Content |
|---|---|
| Tiles | Big number in aubergine (DESIGN.md `card-stat`), one caption line: Applicants "51" / "50 scored"; Qualified "22%" / "11 of 50"; Best score "95" / file name, links to the review; Average "58" / "of 50 scored"; Failed "1" / "couldn't be read". |
| Donut | SVG ring, three slices: qualified (success green), missing a must-have (aubergine-mute), could not score (error). Centre: qualified %. Legend with the three counts. |
| Histogram | 10 aubergine bars on a 0–100 axis with labels 0, 20, 40, 60, 80, 100; each bar has a `<title>` tooltip "60–69: 7 applicants"; empty bands show a 2 px stub. |
| Coverage | Per requirement: MUST/NICE chip, text, bar, "18 of 50 · 36%". |
| Top 5 | Rank, file name, "4/4 must-haves", score; each row links to the review. None qualified: "No one meets every must-have yet. Applicants marked ⚠ in the list are the closest." |

States:
- Loading: skeleton blocks in the same shapes.
- No applicants: "Upload resumes in Setup to see the summary." with a button to Setup.
- Draft job: redirected to Setup (§3).
- Scoring: panels show what is scored so far; the Overview refetches the summary whenever the scored count changes (driven by the page's existing 1-second status polling).

Accessibility: each SVG chart has `role="img"` and an `aria-label` with its numbers in words; legends and coverage rows carry the numbers as text; all text ≥ 11 px; visible focus on every link; no animation beyond the existing 150 ms hover transitions.

## 6. Frontend structure

| File | Change |
|---|---|
| `src/api.ts` | `Summary` type and `getSummary(jobId)` |
| `src/pages/JobPage.tsx` | becomes the shell: loading, polling, left list, job header, view switch by route |
| `src/components/Overview.tsx` | new: fetches the summary, lays out panels and states |
| `src/components/charts.tsx` | new: `Donut`, `Histogram`, `CoverageBars` (plain SVG/CSS) |
| `src/components/SetupView.tsx` | new: `RequirementsEditor` + `ResumeUpload`, moved unchanged |
| `src/components/ApplicantList.tsx` | gains the pinned Overview item and full-height scrolling |
| `src/main.tsx` | adds the `/jobs/:jobId/setup` route |

`ApplicantReview`, `RequirementsEditor`, `ResumeUpload` keep their behaviour.

## 7. Testing

Backend, test-first (`backend/tests/test_store.py`, `test_api.py`):

| Test | Checks |
|---|---|
| `test_summary_empty_job` | zero counts, `null` average and best, `histogram` = ten zeros, one `coverage` entry per requirement with `met` 0 and `scored` 0, empty `top` |
| `test_summary_counts_by_status` | total / scored / queued / failed |
| `test_summary_qualified_needs_every_must` | 4/4 qualifies, 3/4 does not, P exactly 0.5 counts as met |
| `test_summary_no_musts_all_scored_qualify` | job with only nice-to-haves |
| `test_summary_histogram_band_edges` | scores 0, 9, 10, 99, 100 → bands 0, 0, 1, 9, 9 |
| `test_summary_coverage_counts_and_order` | met counts; must first, then position |
| `test_summary_top_is_qualified_only_in_rank_order` | ≤ 5, unqualified skipped, ranking order |
| `test_summary_best_and_average` | best = ranking #1 among scored; average over scored only |
| `test_summary_endpoint` | shape; unknown job → 404 |

Frontend: `npm run build` passes; browser checks with the 51 sample resumes — list fixed and scrolling independently, Overview default, numbers equal `/summary`, histogram tooltip, Top 5 and Best tile open the right review, `/setup` works, a draft job opens on Setup, charts update while scoring; at 375 px the list stacks with its own scroll and nothing scrolls sideways. The impeccable detector runs over changed UI files and its findings are fixed. All 87 existing tests still pass.
