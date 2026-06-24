from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ContactInfo, ProfileMaster, WorkExperience, XYZExperience
from app.services.application import _generate_html, generate_application_package


def _make_llm_mock(html: str) -> MagicMock:
    msg = MagicMock(); msg.content = html
    choice = MagicMock(); choice.message = msg
    completion = MagicMock(); completion.choices = [choice]
    client = MagicMock(); client.chat.completions.create.return_value = completion
    return client


_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com", location="Munich"),
    reference_text="Ada Lovelace — Senior Engineer at TechCorp 2021-2024. Reduced API latency by 40%.",
    cv_prompt="Create a resume for this job: {JOB_DESCRIPTION}\nDesign: two-column HTML.",
    cover_letter_prompt="Write a cover letter for: {JOB_DESCRIPTION}\nFormat: full-width HTML.",
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Engineer",
            start_date=date(2021, 1, 1),
            is_current=True,
            achievements=[XYZExperience(
                action="Reduced latency", metric="by 40%", context="via Redis"
            )],
        )
    ],
)

_JOB = JobPosting(
    id=uuid4(),
    title="Backend Engineer",
    company="Acme GmbH",
    location="Munich",
    description="Python FastAPI role",
    url="https://example.com/job/1",
    source="mock",
)

_MATCH = MatchScore(
    job_id=_JOB.id,
    score=85,
    keywords_found=["Python"],
    keywords_missing=[],
    justification="Good match.",
)

_FAKE_HTML = "<html><body><h1>Ada Lovelace</h1></body></html>"


def test_generate_html_substitutes_job_description():
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt, "English")
    call_kwargs = mock_client.chat.completions.create.call_args
    user_content = call_kwargs.kwargs["messages"][0]["content"]
    assert "Backend Engineer at Acme GmbH" in user_content
    assert "{JOB_DESCRIPTION}" not in user_content


def test_generate_html_includes_reference_text():
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt, "English")
    call_kwargs = mock_client.chat.completions.create.call_args
    user_content = call_kwargs.kwargs["messages"][0]["content"]
    assert "Ada Lovelace" in user_content  # from reference_text
    assert "REFERENCE FILES" in user_content


def test_generate_html_strips_markdown_fences():
    mock_client = _make_llm_mock("```html\n<html><body>test</body></html>\n```")
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt, "English")
    assert result == "<html><body>test</body></html>"
    assert "```" not in result


def test_generate_html_strips_generic_fences():
    mock_client = _make_llm_mock("```\n<html><body>x</body></html>\n```")
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt, "English")
    assert "```" not in result


def test_generate_application_package_structure():
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        pkg = generate_application_package(_PROFILE, _JOB, _MATCH)
    assert pkg["job_id"] == str(_JOB.id)
    assert pkg["resume_html"] == _FAKE_HTML
    assert pkg["cover_letter_html"] == _FAKE_HTML
    assert isinstance(pkg["cover_letter_text"], str)
