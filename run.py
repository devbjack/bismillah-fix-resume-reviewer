"""Start the app: python run.py  (build the frontend first: cd frontend && npm run build)."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", app_dir="backend", host="127.0.0.1", port=8000)
