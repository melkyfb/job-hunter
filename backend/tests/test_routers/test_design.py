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


# ---------- seed-defaults endpoint ----------

def test_seed_defaults_returns_job_id():
    designs = [
        DesignVersion(id=f"d{i}", name=f"{i}. Design", prompt="p", type="resume",
                      html_template="<html><head><meta charset='UTF-8'></head><body></body></html>",
                      is_default=(i == 1))
        for i in range(1, 3)
    ]
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE),
        patch("app.routers.design._repo.save"),
        patch("app.routers.design.seed_default_designs", return_value=designs),
    ):
        r = client.post("/profile/design/seed-defaults")
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_seed_defaults_replaces_existing_default_designs():
    """seed-defaults removes designs matching 'N. ...' name pattern before inserting."""
    existing_default = DesignVersion(
        id="old-default", name="1. Old Design", prompt="old", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>old</body></html>",
        is_default=True,
    )
    custom_design = DesignVersion(
        id="custom-1", name="My Custom Design", prompt="custom", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>custom</body></html>",
    )
    profile_with_designs = _PROFILE.model_copy(update={
        "design_versions": [existing_default, custom_design],
        "active_resume_design_id": "old-default",
    })
    new_design = DesignVersion(
        id="new-1", name="1. Professional Equilibrium", prompt="p", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>new</body></html>",
        is_default=True,
    )
    saved_profiles: list = []

    import time
    with (
        patch("app.routers.design._repo.load", return_value=profile_with_designs),
        patch("app.routers.design._repo.save", side_effect=lambda p: saved_profiles.append(p.model_copy(deep=True))),
        patch("app.routers.design.seed_default_designs", return_value=[new_design]),
    ):
        r = client.post("/profile/design/seed-defaults")
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    # custom design preserved, old default removed, new default added
    saved = saved_profiles[-1]
    ids = [v.id for v in saved.design_versions]
    assert "custom-1" in ids
    assert "old-default" not in ids
    assert "new-1" in ids


def test_seed_defaults_returns_404_if_no_profile():
    from app.repositories.profile_repository import ProfileNotFoundError
    with patch("app.routers.design._repo.load", side_effect=ProfileNotFoundError("no profile")):
        r = client.post("/profile/design/seed-defaults")
    assert r.status_code == 404


# ---------- regenerate endpoint ----------

_DESIGN_WITH_PROMPT = DesignVersion(
    id="regen-id",
    name="1. Professional Equilibrium",
    prompt="Two-column modern design",
    type="resume",
    html_template="<html><head><meta charset='UTF-8'></head><body>old</body></html>",
)
_PROFILE_WITH_REGEN = _PROFILE.model_copy(update={"design_versions": [_DESIGN_WITH_PROMPT]})

_NEW_HTML = (
    '<!DOCTYPE html><html><head><meta charset="UTF-8">'
    "<style>@page{size:A4;margin:0;} body{font-family:Arial,sans-serif;margin:0;padding:0;}"
    " h1{color:#333;font-size:24px;} .section{margin:16px 0;padding:8px;}"
    " .role{font-weight:bold;} .company{color:#666;}</style></head>"
    "<body><div class='container'>"
    "<h1>{{ profile.contact.full_name }}</h1>"
    "<p>{{ profile.contact.email }}</p>"
    "{% for exp in profile.work_experiences %}"
    "<div class='section'><span class='role'>{{ exp.role }}</span></div>"
    "{% endfor %}"
    "{% for sk in profile.skills %}<span>{{ sk.name }}</span>{% endfor %}"
    "</div></body></html>"
)


def test_regenerate_returns_job_id():
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE_WITH_REGEN),
        patch("app.routers.design._repo.save"),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _NEW_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/regen-id/regenerate")
    assert r.status_code == 202
    assert "job_id" in r.json()


def test_regenerate_overwrites_html_preserves_id():
    import time
    saved_profiles: list = []

    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE_WITH_REGEN),
        patch("app.routers.design._repo.save", side_effect=lambda p: saved_profiles.append(p.model_copy(deep=True))),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _NEW_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/regen-id/regenerate")
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    saved_version = next(v for v in saved_profiles[-1].design_versions if v.id == "regen-id")
    assert saved_version.html_template == _NEW_HTML
    assert saved_version.name == "1. Professional Equilibrium"  # preserved
    assert saved_version.prompt == "Two-column modern design"    # preserved


def test_regenerate_returns_404_for_missing_design():
    with patch("app.routers.design._repo.load", return_value=_PROFILE):
        r = client.post("/profile/design/nonexistent-id/regenerate")
    assert r.status_code == 404


def test_regenerate_returns_422_when_no_prompt():
    no_prompt_design = DesignVersion(
        id="no-prompt-id",
        name="Custom",
        prompt="",
        type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body></body></html>",
    )
    profile = _PROFILE.model_copy(update={"design_versions": [no_prompt_design]})
    with patch("app.routers.design._repo.load", return_value=profile):
        r = client.post("/profile/design/no-prompt-id/regenerate")
    assert r.status_code == 422
