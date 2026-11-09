import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from app.pipeline import ReqResult
from app.scorer import ScoreResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, job_text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    text TEXT NOT NULL, type TEXT NOT NULL, weight REAL NOT NULL, position INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS applicants (
    id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    filename TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', error TEXT,
    score INTEGER, must_met INTEGER, must_total INTEGER, flagged INTEGER);
CREATE TABLE IF NOT EXISTS results (
    applicant_id INTEGER NOT NULL REFERENCES applicants(id) ON DELETE CASCADE,
    requirement_id INTEGER NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    probability REAL NOT NULL, evidence TEXT NOT NULL);
"""

APPLICANT_COLS = "id, job_id, filename, status, error, score, must_met, must_total, flagged"


def _applicant(row) -> dict:
    d = dict(row)
    d["flagged"] = None if d["flagged"] is None else bool(d["flagged"])
    return d


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self):
        # one connection per call keeps the store safe to use from the worker thread
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # jobs
    def create_job(self, name: str, job_text: str) -> int:
        with self._conn() as c:
            return c.execute("INSERT INTO jobs (name, job_text, created_at) VALUES (?, ?, ?)",
                             (name, job_text, datetime.now(timezone.utc).isoformat())).lastrowid

    def list_jobs(self) -> list[dict]:
        with self._conn() as c:
            return [dict(r) for r in c.execute(
                "SELECT id, name, status, created_at FROM jobs ORDER BY id DESC")]

    def get_job(self, job_id: int) -> dict | None:
        with self._conn() as c:
            row = c.execute("SELECT id, name, job_text, status, created_at FROM jobs WHERE id = ?",
                            (job_id,)).fetchone()
            if row is None:
                return None
            job = dict(row)
            job["requirements"] = [dict(r) for r in c.execute(
                "SELECT id, text, type, weight FROM requirements WHERE job_id = ? ORDER BY position",
                (job_id,))]
            return job

    def set_requirements(self, job_id: int, reqs: list[dict], confirm: bool = True) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM requirements WHERE job_id = ?", (job_id,))
            c.executemany(
                "INSERT INTO requirements (job_id, text, type, weight, position) VALUES (?, ?, ?, ?, ?)",
                [(job_id, r["text"], r["type"], r["weight"], i) for i, r in enumerate(reqs)])
            if confirm:
                c.execute("UPDATE jobs SET status = 'confirmed' WHERE id = ?", (job_id,))

    def delete_job(self, job_id: int) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))

    # applicants
    def add_applicant(self, job_id: int, filename: str) -> int:
        with self._conn() as c:
            return c.execute("INSERT INTO applicants (job_id, filename) VALUES (?, ?)",
                             (job_id, filename)).lastrowid

    def get_applicant(self, applicant_id: int) -> dict | None:
        with self._conn() as c:
            row = c.execute(f"SELECT {APPLICANT_COLS} FROM applicants WHERE id = ?",
                            (applicant_id,)).fetchone()
            if row is None:
                return None
            app = _applicant(row)
            app["results"] = [dict(r) for r in c.execute(
                "SELECT r.requirement_id, q.text, q.type, q.weight, r.probability, r.evidence "
                "FROM results r JOIN requirements q ON q.id = r.requirement_id "
                "WHERE r.applicant_id = ? ORDER BY q.position", (applicant_id,))]
            return app

    def queued_ids(self) -> list[int]:
        with self._conn() as c:
            return [r[0] for r in c.execute("SELECT id FROM applicants WHERE status = 'queued' ORDER BY id")]

    def save_result(self, applicant_id: int, sr: ScoreResult, results: list[ReqResult]) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM results WHERE applicant_id = ?", (applicant_id,))
            c.executemany("INSERT INTO results VALUES (?, ?, ?, ?)",
                          [(applicant_id, r.requirement_id, r.probability, r.evidence) for r in results])
            c.execute("UPDATE applicants SET status = 'done', error = NULL, score = ?, must_met = ?, "
                      "must_total = ?, flagged = ? WHERE id = ?",
                      (sr.score, sr.must_met, sr.must_total, int(sr.flagged), applicant_id))

    def mark_failed(self, applicant_id: int, error: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM results WHERE applicant_id = ?", (applicant_id,))
            c.execute("UPDATE applicants SET status = 'failed', error = ?, score = NULL, must_met = NULL, "
                      "must_total = NULL, flagged = NULL WHERE id = ?", (error, applicant_id))

    def requeue_job(self, job_id: int) -> list[int]:
        with self._conn() as c:
            c.execute("DELETE FROM results WHERE applicant_id IN (SELECT id FROM applicants WHERE job_id = ?)",
                      (job_id,))
            c.execute("UPDATE applicants SET status = 'queued', error = NULL, score = NULL, must_met = NULL, "
                      "must_total = NULL, flagged = NULL WHERE job_id = ?", (job_id,))
            return [r[0] for r in c.execute("SELECT id FROM applicants WHERE job_id = ? ORDER BY id", (job_id,))]

    def status(self, job_id: int) -> dict:
        with self._conn() as c:
            done, total = c.execute(
                "SELECT COALESCE(SUM(status != 'queued'), 0), COUNT(*) FROM applicants WHERE job_id = ?",
                (job_id,)).fetchone()
            return {"done": done, "total": total}

    def ranking(self, job_id: int) -> list[dict]:
        with self._conn() as c:
            return [_applicant(r) for r in c.execute(
                f"SELECT {APPLICANT_COLS} FROM applicants WHERE job_id = ? ORDER BY "
                "CASE status WHEN 'done' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END, "
                "score DESC, must_met DESC, filename ASC, id ASC", (job_id,))]
