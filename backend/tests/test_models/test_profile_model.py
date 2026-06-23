from __future__ import annotations

from app.models.profile import ProfileMaster, ContactInfo
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT


def test_profile_has_reference_text_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.reference_text == ""


def test_profile_has_cv_prompt_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.cv_prompt == DEFAULT_CV_PROMPT


def test_profile_has_cover_letter_prompt_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.cover_letter_prompt == DEFAULT_CL_PROMPT


def test_profile_has_no_design_fields():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert not hasattr(p, "design_versions")
    assert not hasattr(p, "active_resume_design_id")
    assert not hasattr(p, "active_cover_letter_design_id")
