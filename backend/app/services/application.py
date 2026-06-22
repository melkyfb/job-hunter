from __future__ import annotations

import base64
import logging
from typing import Optional
from uuid import UUID

from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster
from app.services.cover_letter import generate_cover_letter
from app.services.resume_renderer import render_resume_pdf

logger = logging.getLogger(__name__)


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
    resume_design_id: Optional[str] = None,
    cover_letter_design_id: Optional[str] = None,
) -> dict:
    """
    Generates resume PDF + cover letter PDF.
    If design IDs are provided, uses Playwright + Jinja2 HTML templates.
    Falls back to ReportLab for any missing design.
    """
    resume_pdf = _render_resume(profile, job, match, resume_design_id)
    cover_letter_text = generate_cover_letter(profile, job)
    cover_letter_pdf = _render_cover_letter(
        cover_letter_text, profile, job, cover_letter_design_id
    )

    return {
        "job_id": job.id,
        "resume_pdf_base64": _to_b64(resume_pdf),
        "cover_letter_text": cover_letter_text,
        "cover_letter_pdf_base64": _to_b64(cover_letter_pdf),
    }


def _render_resume(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
    design_id: Optional[str],
) -> bytes:
    """Use custom HTML design if available; fall back to ReportLab."""
    version = _find_design(profile, design_id, "resume")
    if version:
        try:
            from app.services.playwright_renderer import (
                build_jinja_context,
                render_html_to_pdf,
                render_template_to_html,
            )
            ctx = build_jinja_context(profile)
            html = render_template_to_html(version.html_template, ctx)
            return render_html_to_pdf(html)
        except Exception as exc:
            logger.warning("Playwright render failed for resume, falling back to ReportLab: %s", exc)

    return render_resume_pdf(profile, highlight_keywords=match.keywords_found)


def _render_cover_letter(
    text: str,
    profile: ProfileMaster,
    job: JobPosting,
    design_id: Optional[str],
) -> bytes:
    """Use custom HTML design if available; fall back to ReportLab."""
    version = _find_design(profile, design_id, "cover_letter")
    if version:
        try:
            from app.services.playwright_renderer import (
                render_cover_letter_template_to_html,
                render_html_to_pdf,
            )
            c = profile.contact
            html = render_cover_letter_template_to_html(
                template=version.html_template,
                letter_body=text,
                job_title=job.title,
                job_company=job.company,
                contact_name=c.full_name,
                contact_email=c.email,
                contact_phone=c.phone or "",
                contact_location=c.location or "",
            )
            return render_html_to_pdf(html)
        except Exception as exc:
            logger.warning("Playwright render failed for cover letter, falling back to ReportLab: %s", exc)

    return _render_cover_letter_pdf_reportlab(text, profile)


def _find_design(profile: ProfileMaster, design_id: Optional[str], design_type: str):
    """Find a DesignVersion by ID, or return None."""
    if design_id:
        for v in profile.design_versions:
            if v.id == design_id and v.type == design_type:
                return v
    # Try active default
    active_id = (
        profile.active_resume_design_id
        if design_type == "resume"
        else profile.active_cover_letter_design_id
    )
    if active_id:
        for v in profile.design_versions:
            if v.id == active_id:
                return v
    return None


def generate_master_resume(profile: ProfileMaster, design_id: Optional[str] = None) -> bytes:
    """Generate master resume PDF, using custom design if provided."""
    version = _find_design(profile, design_id, "resume")
    if version:
        try:
            from app.services.playwright_renderer import (
                build_jinja_context,
                render_html_to_pdf,
                render_template_to_html,
            )
            ctx = build_jinja_context(profile)
            html = render_template_to_html(version.html_template, ctx)
            return render_html_to_pdf(html)
        except Exception:
            pass
    return render_resume_pdf(profile, highlight_keywords=None)


def _render_cover_letter_pdf_reportlab(text: str, profile: ProfileMaster) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25*mm, rightMargin=25*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    accent = colors.HexColor("#4f6ef7")
    body_style = ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                                textColor=colors.HexColor("#1a1a1a"), leading=15, spaceAfter=10)
    header_style = ParagraphStyle("header", fontSize=11, fontName="Helvetica-Bold",
                                  textColor=accent, spaceAfter=16)
    story = [
        Paragraph(profile.contact.full_name, header_style),
        Paragraph(profile.contact.email, body_style),
        Spacer(1, 6*mm),
    ]
    for para in text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para.replace("\n", "<br/>"), body_style))
    doc.build(story)
    return buf.getvalue()
