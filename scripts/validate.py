"""Step 0 gate: compare Julia's verdicts and ranking with hand labels in samples/labels.json."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from sentence_transformers import SentenceTransformer  # noqa: E402

from app.decider import MODEL_DIR, JuliaDecider  # noqa: E402
from app.pdf_text import extract_text  # noqa: E402
from app.pipeline import review  # noqa: E402

device = sys.argv[1] if len(sys.argv) > 1 else "cpu"
labels = json.loads((ROOT / "samples" / "labels.json").read_text(encoding="utf-8"))
reqs = [{**r, "id": i} for i, r in enumerate(labels["requirements"])]
st = SentenceTransformer("BAAI/bge-small-en-v1.5")
embed = lambda texts: st.encode(texts, normalize_embeddings=True)  # noqa: E731
decider = JuliaDecider(str(ROOT / MODEL_DIR), device=device)

agree = total = 0
per_req = [[0, 0] for _ in reqs]
scores, times = {}, []
print(f"{'resume':8}{'score':>6}  P(met) per requirement (* = disagrees with label)")
for name, lab in labels["labels"].items():
    t0 = time.perf_counter()
    sr, results = review(extract_text((ROOT / "samples" / f"{name}.pdf").read_bytes()), reqs, decider, embed)
    times.append(time.perf_counter() - t0)
    scores[name] = (sr.score, sr.must_met)
    cells = []
    for i, (r, want) in enumerate(zip(results, lab)):
        ok = (r.probability >= 0.5) == bool(want)
        agree += ok
        total += 1
        per_req[i][0] += ok
        per_req[i][1] += 1
        cells.append(f"{r.probability:.2f}{' ' if ok else '*'}")
    print(f"{name:8}{sr.score:>6}  " + " ".join(cells))

ranking = sorted(scores, key=lambda n: (-scores[n][0], -scores[n][1], n))
overlap = len(set(ranking[:5]) & set(labels["ranking"][:5]))
agreement = agree / total
print("\nPer-requirement agreement:")
for r, (ok, n) in zip(reqs, per_req):
    print(f"  {ok}/{n}  [{r['type']}] {r['text']}")
print(f"\nApp ranking:  {ranking}")
print(f"Hand ranking: {labels['ranking']}")
print(f"Verdict agreement: {agreement:.0%} (need >= 70%)")
print(f"Top-5 overlap: {overlap}/5 (need >= 4)")
print(f"Seconds per resume: {sum(times) / len(times):.1f} on {device}")
print("GATE:", "PASS" if agreement >= 0.7 and overlap >= 4 else "FAIL")
print("\nTwo-column extraction check (r01, first 300 chars):")
print(extract_text((ROOT / "samples" / "r01.pdf").read_bytes())[:300])
