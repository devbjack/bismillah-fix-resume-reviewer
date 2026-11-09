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
    # sort=True reads blocks by position, which keeps two-column resumes in order
    return "\n".join(page.get_text(sort=True) for page in doc)
