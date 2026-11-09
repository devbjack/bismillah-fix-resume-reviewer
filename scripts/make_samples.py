"""Build samples/*.pdf from samples/src/*.txt. `---COLUMN---` splits a two-column layout."""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parent.parent
SRC, OUT = ROOT / "samples" / "src", ROOT / "samples"
FONT = dict(fontname="helv", fontsize=9.5)


def write(rect, text, page, name):
    if page.insert_textbox(rect, text, **FONT) < 0:
        raise SystemExit(f"{name}: text overflows the page")


def build(name: str, text: str) -> None:
    text = text.replace("—", "-").replace("–", "-")  # base-14 helv lacks these dashes
    doc = pymupdf.open()
    page = doc.new_page()  # A4-ish letter default 612x792
    if "---COLUMN---" in text:
        left, right = text.split("---COLUMN---")
        write(pymupdf.Rect(36, 40, 186, 760), left.strip(), page, name)
        write(pymupdf.Rect(206, 40, 576, 760), right.strip(), page, name)
    else:
        write(pymupdf.Rect(50, 40, 562, 760), text.strip(), page, name)
    doc.save(OUT / f"{name}.pdf")


for src in sorted(SRC.glob("*.txt")):
    build(src.stem, src.read_text(encoding="utf-8"))

# scanned copy of r01: the page as an image only, no text layer
pix = pymupdf.open(OUT / "r01.pdf")[0].get_pixmap(dpi=100)
scan = pymupdf.open()
scan.new_page().insert_image(pymupdf.Rect(0, 0, 612, 792), pixmap=pix)
scan.save(OUT / "r11_scanned.pdf")
print("built", len(list(OUT.glob("*.pdf"))), "PDFs")
