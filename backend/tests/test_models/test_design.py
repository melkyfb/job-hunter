from app.models.design import DesignVersion


def test_design_version_defaults():
    dv = DesignVersion(
        name="Tech Modern",
        prompt="Clean modern blue",
        type="resume",
        html_template="<html></html>",
    )
    assert dv.id  # uuid assigned
    assert len(dv.id) == 36
    assert dv.is_default is False
    assert dv.inherit_from_design_id is None
    assert dv.created_at is not None


def test_design_version_json_roundtrip():
    dv = DesignVersion(
        name="Cover Blue",
        prompt="Elegant cover letter",
        type="cover_letter",
        html_template="<html><body>{{ letter_body }}</body></html>",
        inherit_from_design_id="abc-123",
        is_default=True,
    )
    restored = DesignVersion.model_validate_json(dv.model_dump_json())
    assert restored.name == "Cover Blue"
    assert restored.inherit_from_design_id == "abc-123"
    assert restored.is_default is True
