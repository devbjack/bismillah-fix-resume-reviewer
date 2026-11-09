"""Real app wiring: loads the models once and starts the worker. Imported by uvicorn via run.py."""
from pathlib import Path

from sentence_transformers import SentenceTransformer

from app.api import Deps, create_app
from app.decider import MODEL_DIR, JuliaDecider
from app.req_extract import extract_requirements
from app.store import Store
from app.worker import Worker

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

_embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")


def embed(texts: list[str]):
    return _embedder.encode(texts, normalize_embeddings=True)


store = Store(str(DATA / "app.db"))
worker = Worker(store, DATA / "uploads", JuliaDecider(str(ROOT / MODEL_DIR)), embed)
worker.start()
app = create_app(Deps(store, DATA / "uploads", extract_requirements, worker),
                 static_dir=ROOT / "frontend" / "dist")
