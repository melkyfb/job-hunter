from __future__ import annotations

import io
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup
from docx import Document


def extract_text(filename: str, content: bytes) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _from_pdf(content)
    if ext == ".docx":
        return _from_docx(content)
    if ext in (".html", ".htm"):
        return _from_html(content)
    raise ValueError(f"Unsupported file type: '{ext}'. Use PDF, DOCX, or HTML.")


def _from_pdf(content: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def _from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _from_html(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "meta", "head"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)
