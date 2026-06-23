from __future__ import annotations

import logging
from textwrap import dedent

from app.core.config import settings
from app.core.llm import get_llm_client
from app.services.extractors import extract_text

logger = logging.getLogger(__name__)

_MAX_PER_FILE = 4_000
_MAX_TOTAL = 60_000

_RELEVANCE_SYSTEM = dedent("""\
    You are a career document analyzer. Extract ONLY the career-relevant information from this document.
    Keep: job titles, companies, dates, responsibilities, achievements, skills, technologies, certifications,
          education (degree, institution, dates, relevant courses), languages, and any performance
          or competency assessments.
    Discard: legal boilerplate, company addresses, HR signatures, page numbers, decorative headers,
             privacy notices, and any text not useful for a job application.
    Return the extracted content as clean plain text. If nothing is career-relevant, return an empty string.
    Maximum 4000 characters.
""").strip()


def extract_relevant(filename: str, content: bytes) -> str:
    """Extract raw text from file then filter to career-relevant content via LLM. Returns ≤4000 chars."""
    try:
        raw = extract_text(filename, content)
    except ValueError as exc:
        logger.warning("Skipping %s — unsupported format: %s", filename, exc)
        return ""
    # pdfminer raises non-ValueError exceptions for corrupted files
    except Exception as exc:
        logger.warning("Skipping %s — extraction error: %s", filename, exc)
        return ""

    if not raw.strip():
        return ""

    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=settings.active_model,
            messages=[
                {"role": "system", "content": _RELEVANCE_SYSTEM},
                {"role": "user", "content": raw[:20_000]},  # protect token budget
            ],
            temperature=0,
        )
        extracted = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("LLM relevance extraction failed for %s: %s", filename, exc)
        return ""

    return extracted[:_MAX_PER_FILE]


def compile_reference_text(files: list[tuple[str, bytes]]) -> str:
    """
    Process each (filename, content) pair through extract_relevant,
    concatenate results, and cap total at 60k chars.
    """
    parts: list[str] = []
    total = 0

    for filename, content in files:
        extracted = extract_relevant(filename, content)
        if not extracted:
            continue
        section = f"=== {filename} ===\n{extracted}\n"
        total += len(section)
        parts.append(section)

    compiled = "\n".join(parts)
    if len(compiled) > _MAX_TOTAL:
        compiled = compiled[:_MAX_TOTAL]
        compiled += f"\n[truncated — {total} chars total across {len(parts)} files]"

    return compiled
