from __future__ import annotations

import io

import pytest

from app.services.extractors import extract_text


# ── HTML ──────────────────────────────────────────────────────────────────────

def test_html_extraction_strips_tags():
    html = b"<html><head><style>body{}</style></head><body><h1>Ada Lovelace</h1><p>Engineer</p></body></html>"
    result = extract_text("resume.html", html)
    assert "Ada Lovelace" in result
    assert "Engineer" in result
    assert "<" not in result


def test_html_extraction_removes_script():
    html = b"<html><body><p>Name</p><script>alert('xss')</script></body></html>"
    result = extract_text("resume.htm", html)
    assert "Name" in result
    assert "alert" not in result


# ── DOCX ──────────────────────────────────────────────────────────────────────

def _make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_docx_extraction():
    content = _make_docx(["Ada Lovelace", "Senior Engineer", "Python, FastAPI"])
    result = extract_text("resume.docx", content)
    assert "Ada Lovelace" in result
    assert "Senior Engineer" in result
    assert "Python" in result


def test_docx_ignores_empty_paragraphs():
    content = _make_docx(["Name", "", "   ", "Skills"])
    result = extract_text("resume.docx", content)
    lines = [l for l in result.splitlines() if l.strip()]
    assert lines == ["Name", "Skills"]


# ── TXT / MD ──────────────────────────────────────────────────────────────────

def test_extract_text_accepts_txt():
    result = extract_text("resume.txt", b"Plain text resume content")
    assert result == "Plain text resume content"


def test_extract_text_accepts_md():
    result = extract_text("resume.md", b"# John Doe\n\n## Experience")
    assert "John Doe" in result


# ── Unsupported format ────────────────────────────────────────────────────────

def test_unsupported_extension_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("resume.xyz", b"some text")
