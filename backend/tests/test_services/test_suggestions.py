from __future__ import annotations

import json
from unittest.mock import patch

from tests.conftest import make_llm_mock, sample_profile
import pytest

from app.models.profile import JobSuggestion


def _suggestions_response(n: int = 3) -> str:
    suggestions = [
        {"title": f"Role {i}", "keywords": ["Python", "FastAPI", f"Skill{i}"]}
        for i in range(1, n + 1)
    ]
    return json.dumps({"suggestions": suggestions})


def test_generate_suggestions_returns_list(sample_profile):
    mock = make_llm_mock(_suggestions_response(5))
    with patch("app.services.suggestions.get_llm_client", return_value=mock):
        from app.services.suggestions import generate_suggestions
        result = generate_suggestions(sample_profile)
    assert len(result) == 5
    assert all(isinstance(s, JobSuggestion) for s in result)
    assert result[0].title == "Role 1"
    assert "Python" in result[0].keywords


def test_generate_suggestions_self_corrects_on_bad_json(sample_profile):
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        text = "not json at all" if call_count == 1 else _suggestions_response(2)
        return make_llm_mock(text).chat.completions.create(**kwargs)

    mock = make_llm_mock("placeholder")
    mock.chat.completions.create.side_effect = side_effect

    from app.services.suggestions import generate_suggestions
    with patch("app.services.suggestions.get_llm_client", return_value=mock):
        result = generate_suggestions(sample_profile)

    assert call_count == 2
    assert len(result) == 2


def test_generate_suggestions_returns_empty_on_total_failure(sample_profile):
    mock = make_llm_mock("this is not json {{{")
    with patch("app.services.suggestions.get_llm_client", return_value=mock):
        from app.services.suggestions import generate_suggestions
        result = generate_suggestions(sample_profile)
    # After all retries fail, returns empty list instead of raising
    assert result == []
