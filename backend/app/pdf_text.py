import pymupdf as fitz


def _open(data: bytes) -> fitz.Document:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise ValueError("Not a readable PDF") from e
    if doc.needs_pass or doc.page_count == 0:
        raise ValueError("Not a readable PDF")
    return doc


def is_pdf(data: bytes) -> bool:
    if not data.startswith(b"%PDF"):
        return False
    try:
        _open(data)
        return True
    except ValueError:
        return False


def extract_text(data: bytes) -> str:
    doc = _open(data)
    # Sorted text *blocks* (not lines): plain sort=True merges same-height lines across columns
    parts = []
    for page in doc:
        for block in page.get_text("blocks", sort=True):
            if block[6] == 0:  # text block, not image
                parts.append(block[4].strip())
    return "\n\n".join(p for p in parts if p)
