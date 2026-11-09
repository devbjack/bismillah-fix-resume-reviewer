"""Download Julia 1 into models/Julia-1 and install its runtime into the current venv."""
import subprocess
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parent.parent
target = ROOT / "models" / "Julia-1"
snapshot_download("SupersonicLabs/Julia-1", local_dir=str(target))
weights = target / "model.safetensors"
size_mb = weights.stat().st_size / 1e6
print(f"model.safetensors: {size_mb:.0f} MB")
if size_mb < 100:
    sys.exit("weights look like a Git LFS pointer, not the real file")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-e", str(target)])
print("Julia installed")
