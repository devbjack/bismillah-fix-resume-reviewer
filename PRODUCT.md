# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
One HRD (HR) staff member screening applicants for a single opening, on their own laptop. They have one job-requirement PDF and 10–100 English resume PDFs, and need to decide who gets an interview.

## Product Purpose
An AI-powered resume reviewer that ranks applicants against a job's requirements and shows a 0–100 score with per-requirement evidence. It advises; HRD decides. Success: about 50 resumes ranked in ~5 minutes, a top 5 that matches HRD's own judgment, and every score traceable to requirements and evidence passages. Built as a course project.

## Positioning
Free and fully local (no paid LLM, no cloud). Instead of asking an LLM for a vague overall score, it asks a local LLM (Ollama, qwen2.5:3b) one yes/no question per requirement, reads the model's own probability of answering yes, and shows it plus the resume passage it used, so every number can be checked.

## Operating Context
Flow: create a job from a PDF → the LLM (Ollama) extracts requirements → HRD edits and confirms them (text, must-have/nice-to-have, weight) → upload resumes → background scoring with progress → ranked list beside the selected applicant's review → CSV export. Jobs persist locally and can be deleted with their files.

## Capabilities and Constraints
- English, text-based PDFs only; no OCR, no DOCX.
- Single user, no logins, runs on localhost.
- Never rejects or contacts applicants; flags (⚠) a probably-missing must-have but keeps the applicant listed.
- Applicant label is the file name; names, photos and personal details are not extracted or scored.
- Terminology: job, requirement (must-have / nice-to-have, weight), applicant, score, P(met), evidence, flagged.

## Brand Commitments
Visual language is bound to `ref/DESIGN.md` (user-provided reference).

## Evidence on Hand
Sample job and 10 fictional resumes in `samples/`. No real customers, testimonials or metrics exist; do not invent any.

## Product Principles
- Explain every number: a score without its requirements and evidence is not shown.
- HRD stays in control: requirements are confirmed by a human before anything is scored.
- Honest uncertainty: show probabilities, not verdicts dressed as facts.
- Nothing hidden: failed or flagged applicants stay visible with the reason.

## Accessibility & Inclusion
Keyboard-operable, visible focus, WCAG AA contrast; met/not-met never conveyed by color alone.
