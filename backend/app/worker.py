from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
from pathlib import Path

from app.decider import Decider, DeciderUnavailable
from app.pdf_text import extract_text
from app.pipeline import NoTextError, review
from app.retriever import Embed
from app.store import Store

log = logging.getLogger(__name__)
NO_TEXT = "No text found — scanned PDF?"
OLLAMA_DOWN = "Couldn't reach Ollama — start it, then save the requirements again to re-score."


class Worker:
    """One background thread that scores queued applicants one at a time."""

    def __init__(self, store: Store, uploads_dir: Path, decider: Decider, embed: Embed):
        self.store = store
        self.uploads_dir = Path(uploads_dir)
        self.decider = decider
        self.embed = embed
        self.q: queue.Queue[int] = queue.Queue()
        self._pending: set[int] = set()
        self._lock = threading.Lock()

    def start(self) -> None:
        self.enqueue(self.store.queued_ids())  # pick up work left by a previous run
        threading.Thread(target=self._run, daemon=True, name="scoring-worker").start()

    def enqueue(self, ids: list[int]) -> None:
        with self._lock:
            for i in ids:
                if i not in self._pending:
                    self._pending.add(i)
                    self.q.put(i)

    def join_idle(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        with self.q.all_tasks_done:
            while self.q.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("worker did not go idle")
                self.q.all_tasks_done.wait(remaining)

    def _run(self) -> None:
        while True:
            applicant_id = self.q.get()
            with self._lock:
                self._pending.discard(applicant_id)
            try:
                self.process(applicant_id)
            except Exception:  # never let one resume kill the worker
                log.exception("worker crashed on applicant %s", applicant_id)
            finally:
                self.q.task_done()

    def process(self, applicant_id: int) -> None:
        app = self.store.get_applicant(applicant_id)
        job = app and self.store.get_job(app["job_id"])
        if not job:
            return  # deleted meanwhile
        path = self.uploads_dir / str(job["id"]) / f"{applicant_id}.pdf"
        try:
            sr, results = review(extract_text(path.read_bytes()), job["requirements"], self.decider, self.embed)
        except NoTextError:
            self.store.mark_failed(applicant_id, NO_TEXT)
        except DeciderUnavailable:
            self.store.mark_failed(applicant_id, OLLAMA_DOWN)
        except Exception as e:
            self.store.mark_failed(applicant_id, str(e) or type(e).__name__)
        else:
            try:
                self.store.save_result(applicant_id, sr, results)
            except sqlite3.IntegrityError:
                pass  # requirements changed (or job deleted) mid-scoring; the applicant is already requeued
