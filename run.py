"""Start the app: python run.py  (build the frontend first: cd frontend && npm run build)."""
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", app_dir=str(Path(__file__).parent / "backend"), host="127.0.0.1", port=8000)
