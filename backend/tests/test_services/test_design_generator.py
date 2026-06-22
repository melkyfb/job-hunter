import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.design_generator import generate_cover_letter_template, generate_resume_template

_VALID_RESUME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 20mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; margin: 0; padding: 0; }
h1 { font-size: 22pt; font-weight: bold; color: #1a3a5c; margin-bottom: 4px; }
h2 { font-size: 13pt; color: #1a3a5c; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
.contact { font-size: 10pt; color: #555; margin-bottom: 12px; }
.section { margin-bottom: 16px; }
.role { font-weight: bold; }
.dates { font-size: 10pt; color: #777; float: right; }
ul { margin: 4px 0; padding-left: 18px; }
li { margin-bottom: 2px; }
.skill-list { display: flex; flex-wrap: wrap; gap: 6px; }
.skill { background: #e8f0fe; padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
</style>
</head>
<body>
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">
{{ profile.contact.email }}{% if profile.contact.phone %} · {{ profile.contact.phone }}{% endif %}
{% if profile.contact.location %} · {{ profile.contact.location }}{% endif %}
</div>
{% if profile.summary %}<div class="section"><p>{{ profile.summary }}</p></div>{% endif %}
<div class="section">
<h2>Experience</h2>
{% for exp in profile.work_experiences %}
<div>
<span class="role">{{ exp.role }}</span> — {{ exp.company }}
<span class="dates">{{ exp.start_date }} – {{ "Present" if exp.is_current else exp.end_date }}</span>
<ul>{% for a in exp.achievements %}<li>{{ a }}</li>{% endfor %}</ul>
</div>
{% endfor %}
</div>
<div class="section">
<h2>Skills</h2>
<div class="skill-list">{% for sk in profile.skills %}<span class="skill">{{ sk.name }}</span>{% endfor %}</div>
</div>
<div class="section">
<h2>Education</h2>
{% for edu in profile.education %}<p>{{ edu.degree }} — {{ edu.institution }}, {{ edu.end_year }}</p>{% endfor %}
</div>
<div class="section">
<h2>Languages</h2>
{% for lang in profile.languages %}<span>{{ lang.name }} ({{ lang.proficiency }})</span>{% endfor %}
</div>
</body>
</html>"""

_VALID_CL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 25mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
h1 { font-size: 18pt; color: #1a3a5c; }
.contact { font-size: 10pt; color: #555; margin-bottom: 20px; }
.header { border-bottom: 2px solid #1a3a5c; padding-bottom: 8px; margin-bottom: 16px; }
.body-text p { margin-bottom: 12px; line-height: 1.6; }
.signature { margin-top: 24px; }
</style>
</head>
<body>
<div class="header">
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">
{{ profile.contact.email }}{% if profile.contact.phone %} · {{ profile.contact.phone }}{% endif %}
</div>
</div>
<div class="body-text">
{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}
</div>
<div class="signature"><p>Atenciosamente,<br>{{ profile.contact.full_name }}</p></div>
</body>
</html>"""


def _make_mock_client(html: str):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({"html_template": html})
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_generate_resume_template_returns_valid_html():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_RESUME_HTML)):
        result = generate_resume_template("Modern blue tech resume", profile)

    assert "<!DOCTYPE html>" in result
    assert "{{ profile.contact.full_name }}" in result


def test_generate_resume_template_self_corrects_on_bad_jinja():
    """First response has broken Jinja2; second response is valid."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    bad_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 20mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
h1 { font-size: 22pt; font-weight: bold; }
h2 { font-size: 13pt; }
.contact { font-size: 10pt; color: #555; margin-bottom: 12px; }
.section { margin-bottom: 16px; }
.skill { background: #e8f0fe; padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
</style>
</head>
<body>
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">{{ profile.contact.email }}</div>
{% broken_jinja_tag %}
<div class="section"><h2>Experience</h2>
{% for exp in profile.work_experiences %}
<p>{{ exp.role }} at {{ exp.company }}</p>
{% endfor %}
</div>
</body>
</html>"""
    mock_client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]),
    ]
    mock_client.chat.completions.create.side_effect = responses

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client), \
         patch("app.services.design_generator._check_design_intent"):
        result = generate_resume_template("Modern blue", profile)

    assert mock_client.chat.completions.create.call_count == 2
    assert "<!DOCTYPE html>" in result


def test_generate_resume_template_raises_after_max_retries():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    bad_html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 20mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
h1 { font-size: 22pt; font-weight: bold; }
h2 { font-size: 13pt; }
.contact { font-size: 10pt; color: #555; margin-bottom: 12px; }
.section { margin-bottom: 16px; }
.skill { background: #e8f0fe; padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
</style>
</head>
<body>
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">{{ profile.contact.email }}</div>
{% broken_jinja_tag %}
<div class="section"><h2>Experience</h2>
{% for exp in profile.work_experiences %}
<p>{{ exp.role }} at {{ exp.company }}</p>
{% endfor %}
</div>
</body>
</html>"""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]
    )

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client), \
         patch("app.services.design_generator._check_design_intent"):
        with pytest.raises(RuntimeError, match="failed to generate a valid"):
            generate_resume_template("Modern blue", profile)

    assert mock_client.chat.completions.create.call_count == 3


def test_generate_cover_letter_template_basic():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_CL_HTML)):
        result = generate_cover_letter_template("Elegant letter", profile, inherit_from_html=None)

    assert "letter_body" in result


def test_generate_cover_letter_template_with_inherited_css():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    resume_html = "<html><head><style>.sidebar { background: blue; }</style></head><body></body></html>"

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_CL_HTML)):
        result = generate_cover_letter_template("Match resume", profile, inherit_from_html=resume_html)

    # The inherited CSS is passed to the LLM (we can't assert it's in the output,
    # but we can verify the function completes without error)
    assert result


# ── DesignGenerationResponse Pydantic validation ──────────────────────────────

def test_pydantic_rejects_missing_doctype():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    with pytest.raises(ValidationError, match="HTML incompleto"):
        DesignGenerationResponse(html_template="<html><head><meta charset='UTF-8'></head><body>hello world this is a long enough string to pass the length check but missing doctype tag completely</body></html>")


def test_pydantic_rejects_missing_charset():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    # Build HTML > 500 chars but without charset meta
    long_html = "<!DOCTYPE html><html><head><style>body{font-family:Arial;}</style></head><body>" + "x" * 450 + "</body></html>"
    with pytest.raises(ValidationError, match="UTF-8"):
        DesignGenerationResponse(html_template=long_html)


def test_pydantic_rejects_too_short():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    short_html = '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>hi</body></html>'
    with pytest.raises(ValidationError, match="500"):
        DesignGenerationResponse(html_template=short_html)


def test_pydantic_accepts_valid_html():
    from app.services.design_generator import DesignGenerationResponse
    result = DesignGenerationResponse(html_template=_VALID_RESUME_HTML)
    assert "<!DOCTYPE" in result.html_template


def test_clean_html_collapses_excessive_newlines():
    from app.services.design_generator import _clean_html
    dirty = "<!DOCTYPE html>\n\n\n\n\n<html>\n\n\n<body>hello</body></html>"
    result = _clean_html(dirty)
    assert "\n\n\n" not in result
    assert "<!DOCTYPE html>" in result


def test_clean_html_removes_literal_escape_sequences():
    from app.services.design_generator import _clean_html
    dirty = "<!DOCTYPE html><html><body>line1\\nline2\\nline3</body></html>"
    result = _clean_html(dirty)
    assert "\\n" not in result


def test_retry_uses_informative_message_on_pydantic_failure():
    """When Pydantic validation fails, the retry message includes the specific error."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    # First response: HTML that fails Pydantic (too short, missing charset)
    bad_html = "<html><head></head><body>short</body></html>"
    mock_client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]),
    ]
    mock_client.chat.completions.create.side_effect = responses

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client), \
         patch("app.services.design_generator._check_design_intent"):
        result = generate_resume_template("Blue sidebar", profile)

    assert mock_client.chat.completions.create.call_count == 2
    # The second call's messages should contain the error from the first attempt
    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    # Find the user correction message
    correction_msgs = [m for m in second_call_messages if m["role"] == "user" and "rejected" in m["content"]]
    assert len(correction_msgs) == 1
