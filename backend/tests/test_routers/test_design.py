from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import DesignVersion
from app.models.profile import ContactInfo, ProfileMaster

client = TestClient(app)

_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com")
)

_VALID_HTML = """<!DOCTYPE html><html><head><style>@page{size:A4;margin:0}</style></head>
<body><h1>{{ profile.contact.full_name }}</h1>
{% for exp in profile.work_experiences %}<p>{{ exp.role }}</p>{% endfor %}
{% for sk in profile.skills %}<span>{{ sk.name }}</span>{% endfor %}
{% for edu in profile.education %}<p>{{ edu.degree }}</p>{% endfor %}
{% for lang in profile.languages %}<p>{{ lang.name }}</p>{% endfor %}
</body></html>"""


def test_post_resume_design_returns_job_id():
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE),
        patch("app.routers.design._repo.save"),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _VALID_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/resume", json={"prompt": "Modern blue"})
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_get_preview_html_returns_rendered_html():
    version = DesignVersion(
        id="test-id-preview",
        name="Test",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with patch("app.routers.design._repo.load", return_value=profile_with_design):
        r = client.get("/profile/design/test-id-preview/preview-html")
    assert r.status_code == 200
    assert "Ada Lovelace" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_delete_design_removes_version():
    version = DesignVersion(
        id="test-id-delete",
        name="To Delete",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with (
        patch("app.routers.design._repo.load", return_value=profile_with_design),
        patch("app.routers.design._repo.save") as mock_save,
    ):
        r = client.delete("/profile/design/test-id-delete")
    assert r.status_code == 204
    saved_profile = mock_save.call_args[0][0]
    assert len(saved_profile.design_versions) == 0


def test_patch_design_updates_name():
    version = DesignVersion(
        id="test-id-patch",
        name="Old Name",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with (
        patch("app.routers.design._repo.load", return_value=profile_with_design),
        patch("app.routers.design._repo.save") as mock_save,
    ):
        r = client.patch("/profile/design/test-id-patch", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_get_preview_html_404_on_unknown_id():
    with patch("app.routers.design._repo.load", return_value=_PROFILE):
        r = client.get("/profile/design/nonexistent-id/preview-html")
    assert r.status_code == 404
