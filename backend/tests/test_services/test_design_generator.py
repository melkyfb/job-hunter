import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.design_generator import generate_resume_template, generate_cover_letter_template


_VALID_RESUME_HTML = """<!DOCTYPE html><html><head><style>
@page { size: A4; margin: 0; }
body { font-family: Arial; }
</style></head><body>
<h1>{{ profile.contact.full_name }}</h1>
<p>{{ profile.contact.email }}</p>
{% for exp in profile.work_experiences %}
<h2>{{ exp.role }} at {{ exp.company }}</h2>
{% for b in exp.achievements %}<p>{{ b }}</p>{% endfor %}
{% endfor %}
{% for sk in profile.skills %}<span>{{ sk.name }}</span>{% endfor %}
{% for edu in profile.education %}<p>{{ edu.degree }}</p>{% endfor %}
{% for lang in profile.languages %}<p>{{ lang.name }}</p>{% endfor %}
</body></html>"""

_VALID_CL_HTML = """<!DOCTYPE html><html><head><style>
@page { size: A4; margin: 0; }
</style></head><body>
<h1>{{ profile.contact.full_name }}</h1>
{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}
</body></html>"""


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

    bad_html = "<html>{% broken %}</html>"
    mock_client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]),
    ]
    mock_client.chat.completions.create.side_effect = responses

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        result = generate_resume_template("Modern blue", profile)

    assert mock_client.chat.completions.create.call_count == 2
    assert "<!DOCTYPE html>" in result


def test_generate_resume_template_raises_after_max_retries():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    bad_html = "<html>{% broken %}</html>"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]
    )

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
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
