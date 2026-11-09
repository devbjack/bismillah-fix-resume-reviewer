import pymupdf as fitz
import pytest

from app.pdf_text import extract_text, is_pdf


def pdf_with(text: str) -> bytes:
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def blank_page_pdf() -> bytes:
    doc = fitz.open()
    doc.new_page()
    return doc.tobytes()


def test_extract_text_returns_page_text():
    assert "Python developer" in extract_text(pdf_with("Python developer"))


def test_extract_text_empty_for_imageonly_pdf():
    assert extract_text(blank_page_pdf()).strip() == ""


def test_extract_text_rejects_non_pdf():
    with pytest.raises(ValueError, match="Not a readable PDF"):
        extract_text(b"hello, I am a .docx")


def test_extract_text_rejects_encrypted_pdf():
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "secret")
    data = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    with pytest.raises(ValueError, match="Not a readable PDF"):
        extract_text(data)


def test_two_column_text_is_not_interleaved():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(36, 40, 186, 400), "SKILLS\nPython\nDocker")
    page.insert_textbox(fitz.Rect(206, 40, 576, 400), "EXPERIENCE\nBackend Engineer at Acme")
    text = extract_text(doc.tobytes())
    assert "SKILLS\nPython\nDocker" in text
    assert "EXPERIENCE\nBackend Engineer at Acme" in text


def test_is_pdf():
    assert is_pdf(pdf_with("x"))
    assert not is_pdf(b"PK\x03\x04")
    assert not is_pdf(b"%PDF-1.7 truncated garbage")
