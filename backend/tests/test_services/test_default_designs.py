from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.services.default_designs import DEFAULT_TEMPLATES, seed_default_designs


def _fake_html(name: str) -> str:
    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f'<style>@page{{size:A4;margin:0}}</style></head>'
        f'<body><h1>{{{{ profile.contact.full_name }}}}</h1>'
        f'<p>{name}</p>'
        f'{{% for exp in profile.work_experiences %}}<div>{{{{ exp.role }}}}</div>{{% endfor %}}'
        f'</body></html>'
    )


def test_default_templates_has_15_entries():
    assert len(DEFAULT_TEMPLATES) == 15


def test_default_templates_names_are_numbered():
    for i, (name, _) in enumerate(DEFAULT_TEMPLATES, start=1):
        assert name.startswith(f"{i}. "), f"Template {i} name must start with '{i}. ', got: {name!r}"


def test_default_templates_prompts_non_empty():
    for name, prompt in DEFAULT_TEMPLATES:
        assert len(prompt) > 30, f"Prompt for '{name}' is too short: {prompt!r}"


def test_seed_default_designs_returns_all_on_success():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    assert len(results) == 15


def test_seed_default_designs_first_is_default():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    assert results[0].is_default is True
    for r in results[1:]:
        assert r.is_default is False


def test_seed_default_designs_preserves_order():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    for i, (expected_name, _) in enumerate(DEFAULT_TEMPLATES):
        assert results[i].name == expected_name


def test_seed_default_designs_skips_failed_template():
    call_count = 0

    def flaky(prompt, skip_intent_check=False):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise RuntimeError("LLM timeout")
        return _fake_html(prompt[:20])

    with patch("app.services.default_designs.generate_resume_template", side_effect=flaky):
        results = seed_default_designs()
    assert len(results) == 14  # one skipped
    # Position 3 (index 2) is missing; result[2] name must be template[3]
    assert results[2].name == DEFAULT_TEMPLATES[3][0]


def test_seed_default_designs_empty_on_all_failures():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=RuntimeError("all fail"),
    ):
        results = seed_default_designs()
    assert results == []


def test_seed_default_designs_calls_progress_fn():
    calls: list[tuple[int, int]] = []

    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        seed_default_designs(progress_fn=lambda done, total: calls.append((done, total)))

    assert len(calls) == 15
    totals = {t for _, t in calls}
    assert totals == {15}
    dones = sorted(d for d, _ in calls)
    assert dones == list(range(1, 16))


def test_seed_default_designs_uses_skip_intent_check():
    """Must call generate_resume_template with skip_intent_check=True."""
    captured_kwargs: list[dict] = []

    def fake_gen(prompt, skip_intent_check=False):
        captured_kwargs.append({"skip_intent_check": skip_intent_check})
        return _fake_html(prompt[:20])

    with patch("app.services.default_designs.generate_resume_template", side_effect=fake_gen):
        seed_default_designs()

    assert all(kw["skip_intent_check"] is True for kw in captured_kwargs)
