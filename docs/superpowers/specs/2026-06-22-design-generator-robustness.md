# Design Generator Robustness — Spec

**Date:** 2026-06-22
**Status:** Approved for implementation

---

## Overview

The current `design_generator.py` sometimes receives vague or non-design inputs from users (e.g., "olá", "qualquer coisa") and either returns an incomplete HTML or fails silently. This spec hardens the generation pipeline with:

1. An **intent check** that rejects non-design prompts before spending tokens on generation
2. A **Pydantic model** (`DesignGenerationResponse`) that validates the LLM's raw output in a single step
3. A **stronger system prompt** that enforces HTML-only, UTF-8, complete document output
4. **Informative retry messages** that tell the LLM exactly what was missing

---

## 1. Intent Check

Before calling the generation LLM, a lightweight classification call determines whether the user's input describes a visual design.

**System prompt (intent classifier):**
```
You are a strict classifier. Determine if the user's text is a resume/cover letter design brief.
A design brief describes visual aspects: layout, colors, fonts, sections, columns, style, or aesthetic.
Return ONLY a JSON object: {"is_design_prompt": true, "hint": ""}
If it IS a design brief, set is_design_prompt=true and hint="".
If it is NOT a design brief (greetings, questions, random text, vague words without visual meaning),
set is_design_prompt=false and hint="<short Portuguese suggestion telling the user what to describe>".
No markdown. No explanation. Only JSON.
```

**Pydantic model for the classifier response:**
```python
class DesignIntentResponse(BaseModel):
    is_design_prompt: bool
    hint: str = ""
```

**Behavior:**
- If `is_design_prompt=False`: raise `ValueError(hint)` immediately — the job fails with the hint as the error message, no generation attempted.
- If `is_design_prompt=True`: proceed to generation.

**Example hint (when user types "olá"):**
> "Descreva o visual do currículo: cores, fontes, layout (uma coluna, sidebar), estilo profissional ou criativo."

---

## 2. Pydantic Validation Model

Replace the two separate functions `_extract_html_template` + `_validate_template` with a single Pydantic model that parses and validates in one step.

```python
from pydantic import BaseModel, field_validator

class DesignGenerationResponse(BaseModel):
    html_template: str

    @field_validator("html_template")
    @classmethod
    def must_be_valid_html(cls, v: str) -> str:
        v = v.strip()
        required = ["<!doctype", "<html", "<head", "<body", "</html>"]
        missing = [tag for tag in required if tag not in v.lower()]
        if missing:
            raise ValueError(f"HTML incompleto — faltando: {missing}")
        if len(v) < 500:
            raise ValueError("HTML muito curto para ser um template completo (mínimo 500 caracteres)")
        if "<meta charset" not in v.lower() and "utf-8" not in v.lower():
            raise ValueError("HTML deve incluir <meta charset=\"UTF-8\"> no <head>")
        return v
```

**Usage in generation loop:**
```python
try:
    parsed = DesignGenerationResponse.model_validate_json(last_raw)
    template = parsed.html_template
except ValidationError as exc:
    last_error = str(exc)
    continue
```

This replaces the existing `_extract_html_template` and `_validate_template` calls entirely. The Jinja2 render check (`render_template_to_html`) remains as a second validation step after Pydantic passes.

---

## 3. Stronger System Prompt

Add the following block at the **very beginning** of both `_RESUME_SYSTEM_PROMPT` and `_COVER_LETTER_SYSTEM_PROMPT` (before existing content):

```
CRITICAL OUTPUT RULES — violating any of these causes the response to be rejected:
1. Return ONLY a JSON object: {"html_template": "..."}. No markdown. No explanation. No code fences.
2. The html_template value MUST be a complete HTML document starting with <!DOCTYPE html>.
3. Include <meta charset="UTF-8"> inside <head>.
4. The HTML must contain <html>, <head>, <body>, and </html> tags.
5. Minimum length: 500 characters of actual HTML content.
6. If the design brief is vague, invent sensible professional defaults — always return a complete HTML.
7. Never return partial HTML, never truncate the output.
```

---

## 4. Informative Retry Messages

When a retry is needed (Pydantic validation or Jinja2 render fails), the message sent back to the LLM includes the specific error:

```python
# On retry:
messages.append({"role": "assistant", "content": last_raw})
messages.append({
    "role": "user",
    "content": (
        f"Your response was rejected. Reason:\n{last_error}\n\n"
        "Fix the issue and return a corrected JSON object: {\"html_template\": \"...complete HTML...\"}\n"
        "Remember: complete HTML document, <!DOCTYPE html>, <meta charset=\"UTF-8\">, no truncation."
    ),
})
```

---

## 5. Scope

**File modified:** `backend/app/services/design_generator.py` only.

No changes to:
- API routes or request/response schemas
- Frontend
- `playwright_renderer.py`
- `app/models/design.py`

The `DesignIntentResponse` and `DesignGenerationResponse` models are defined inline in `design_generator.py` (they are private implementation details, not shared models).

---

## 6. Error Flow

```
User submits prompt
  → Intent check (lightweight LLM call)
    → is_design_prompt=false → raise ValueError(hint) → job fails with hint message
    → is_design_prompt=true → proceed

  → Generation loop (up to _MAX_RETRIES=3):
      → LLM generates response
      → DesignGenerationResponse.model_validate_json(raw)
          → ValidationError → append error to messages, retry
      → render_template_to_html(template, dummy_ctx)
          → Jinja2 error → append error to messages, retry
      → return template ✓

  → All retries exhausted → raise RuntimeError with last error
```

---

## 7. Testing

- `test_design_generator.py`: add tests for:
  - `test_intent_check_rejects_non_design_prompt` — mock LLM returns `is_design_prompt=false`, expect `ValueError` with hint
  - `test_intent_check_passes_design_prompt` — mock returns `true`, generation proceeds
  - `test_pydantic_rejects_incomplete_html` — `DesignGenerationResponse` raises on HTML missing `</html>`
  - `test_pydantic_rejects_missing_charset` — raises on missing UTF-8 meta tag
  - `test_pydantic_rejects_too_short` — raises on HTML < 500 chars
  - `test_retry_on_pydantic_failure` — first call returns bad JSON, second returns valid HTML, expect success
