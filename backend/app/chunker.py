def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 40:
        return False
    return s.endswith(":") or (s.isupper() and any(c.isalpha() for c in s))


def _paragraphs(text: str) -> list[tuple[bool, str]]:
    """(starts_with_heading, paragraph) split at blank lines and before heading lines."""
    paras: list[tuple[bool, list[str]]] = []
    current: list[str] = []
    heading = False
    for line in text.splitlines():
        if not line.strip() or _is_heading(line):
            if current:
                paras.append((heading, current))
            current, heading = [], False
            if not line.strip():
                continue
            heading = True
        current.append(line.rstrip())
    if current:
        paras.append((heading, current))
    return [(h, "\n".join(lines).strip()) for h, lines in paras]


def _hard_split(chunk: str, hard_max: int) -> list[str]:
    if len(chunk) <= hard_max:
        return [chunk]
    pieces, cur = [], ""
    for word in chunk.split():
        if cur and len(cur) + 1 + len(word) > hard_max:
            pieces.append(cur)
            cur = ""
        cur = f"{cur} {word}" if cur else word
        while len(cur) > hard_max:  # a single word longer than hard_max
            pieces.append(cur[:hard_max])
            cur = cur[hard_max:]
    if cur:
        pieces.append(cur)
    return pieces


def chunk_text(text: str, target: int = 1000, hard_max: int = 1500) -> list[str]:
    chunks: list[str] = []
    cur = ""
    for heading, para in _paragraphs(text):
        if cur and (heading or len(cur) + 2 + len(para) > target):
            chunks.append(cur)
            cur = ""
        cur = f"{cur}\n\n{para}" if cur else para
    if cur:
        chunks.append(cur)
    return [piece for c in chunks for piece in _hard_split(c, hard_max)]
