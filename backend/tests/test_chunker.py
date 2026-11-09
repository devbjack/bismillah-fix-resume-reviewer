from app.chunker import chunk_text


def para(n: int, word: str = "word") -> str:
    # a paragraph of exactly n characters
    return (word + " ") * (n // (len(word) + 1)) + "x" * (n % (len(word) + 1))


def test_splits_on_blank_lines_and_merges_small():
    text = "\n\n".join(para(300) for _ in range(3))
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert len(chunks[0]) <= 1000


def test_new_chunk_when_target_exceeded():
    text = "\n\n".join(para(600) for _ in range(3))
    assert len(chunk_text(text)) == 3


def test_heading_line_starts_new_chunk():
    text = "SKILLS\nPython, SQL\nEXPERIENCE\nBackend Engineer at Acme, 2020-2024"
    chunks = chunk_text(text)
    assert len(chunks) == 2
    assert chunks[0].startswith("SKILLS")
    assert chunks[1].startswith("EXPERIENCE")


def test_colon_line_is_heading():
    chunks = chunk_text("Summary:\nI build APIs.\nEducation:\nBSc Computer Science")
    assert [c.split("\n")[0] for c in chunks] == ["Summary:", "Education:"]


def test_hard_splits_long_paragraph():
    chunks = chunk_text("a " * 2000)
    assert len(chunks) > 1
    assert all(len(c) <= 1500 for c in chunks)
    assert "".join(c.replace(" ", "") for c in chunks) == "a" * 2000


def test_empty_text():
    assert chunk_text("  \n ") == []
