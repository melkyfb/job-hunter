from __future__ import annotations

import io
from textwrap import wrap
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models.profile import ProfileMaster, WorkExperience

# ── Design tokens ─────────────────────────────────────────────────────────────
_ACCENT = colors.HexColor("#4f6ef7")
_TEXT = colors.HexColor("#1a1a1a")
_MUTED = colors.HexColor("#555555")
_PAGE_W, _PAGE_H = A4
_MARGIN = 18 * mm


def _styles():
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle("name", fontSize=22, fontName="Helvetica-Bold", textColor=_ACCENT, spaceAfter=2),
        "contact": ParagraphStyle("contact", fontSize=9, fontName="Helvetica", textColor=_MUTED, spaceAfter=8),
        "summary": ParagraphStyle("summary", fontSize=10, fontName="Helvetica", textColor=_TEXT, spaceAfter=12, leading=14),
        "section": ParagraphStyle("section", fontSize=11, fontName="Helvetica-Bold", textColor=_ACCENT, spaceBefore=10, spaceAfter=4),
        "role": ParagraphStyle("role", fontSize=10, fontName="Helvetica-Bold", textColor=_TEXT),
        "company": ParagraphStyle("company", fontSize=9, fontName="Helvetica", textColor=_MUTED, spaceAfter=3),
        "bullet": ParagraphStyle("bullet", fontSize=9, fontName="Helvetica", textColor=_TEXT, leading=13, leftIndent=10, spaceAfter=2),
        "skill": ParagraphStyle("skill", fontSize=9, fontName="Helvetica", textColor=_TEXT),
        "edu": ParagraphStyle("edu", fontSize=9, fontName="Helvetica", textColor=_TEXT, spaceAfter=2),
    }


def _date_range(exp: WorkExperience) -> str:
    start = exp.start_date.strftime("%b %Y")
    end = "Present" if exp.is_current else (exp.end_date.strftime("%b %Y") if exp.end_date else "")
    return f"{start} – {end}"


def _contact_line(profile: ProfileMaster) -> str:
    c = profile.contact
    parts = [c.email]
    if c.phone:
        parts.append(c.phone)
    if c.location:
        parts.append(c.location)
    if c.linkedin_url:
        parts.append(c.linkedin_url.replace("https://", ""))
    if c.github_url:
        parts.append(c.github_url.replace("https://", ""))
    return "  •  ".join(parts)


def render_resume_pdf(
    profile: ProfileMaster,
    highlight_keywords: Optional[list[str]] = None,
) -> bytes:
    """
    Renders ProfileMaster as a professional A4 PDF.
    highlight_keywords: if provided (job-tailored mode), bold those words in bullets.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_MARGIN,
        rightMargin=_MARGIN,
        topMargin=_MARGIN,
        bottomMargin=_MARGIN,
    )

    s = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(profile.contact.full_name, s["name"]))
    story.append(Paragraph(_contact_line(profile), s["contact"]))
    story.append(HRFlowable(width="100%", thickness=1, color=_ACCENT, spaceAfter=8))

    # ── Summary ───────────────────────────────────────────────────────────────
    if profile.summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", s["section"]))
        story.append(Paragraph(profile.summary, s["summary"]))

    # ── Experience ────────────────────────────────────────────────────────────
    if profile.work_experiences:
        story.append(Paragraph("EXPERIENCE", s["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))

        for exp in profile.work_experiences:
            # Role + date on same line via a 2-column table
            header = Table(
                [[Paragraph(exp.role, s["role"]), Paragraph(_date_range(exp), s["company"])]],
                colWidths=[None, 40 * mm],
            )
            header.setStyle(TableStyle([
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]))
            story.append(header)
            story.append(Paragraph(f"{exp.company}{' · ' + exp.location if exp.location else ''}", s["company"]))

            for ach in exp.achievements:
                bullet_text = ach.as_bullet
                if highlight_keywords:
                    for kw in highlight_keywords:
                        bullet_text = bullet_text.replace(kw, f"<b>{kw}</b>")
                story.append(Paragraph(f"• {bullet_text}", s["bullet"]))

            if exp.technologies:
                techs = ", ".join(exp.technologies)
                story.append(Paragraph(f"<i>Technologies:</i> {techs}", s["bullet"]))

            story.append(Spacer(1, 4 * mm))

    # ── Skills ────────────────────────────────────────────────────────────────
    if profile.skills:
        story.append(Paragraph("SKILLS", s["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))
        skill_names = [f"{sk.name} ({sk.level.value})" for sk in profile.skills]
        # 3-column grid
        rows = [skill_names[i:i+3] for i in range(0, len(skill_names), 3)]
        padded = [r + [""] * (3 - len(r)) for r in rows]
        table = Table([[Paragraph(c, s["skill"]) for c in row] for row in padded])
        table.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(table)
        story.append(Spacer(1, 4 * mm))

    # ── Education ─────────────────────────────────────────────────────────────
    if profile.education:
        story.append(Paragraph("EDUCATION", s["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))
        for edu in profile.education:
            end = edu.end_date.strftime("%Y") if edu.end_date else "Present"
            story.append(Paragraph(
                f"<b>{edu.degree} in {edu.field_of_study}</b> — {edu.institution} ({end})",
                s["edu"],
            ))

    # ── Languages ─────────────────────────────────────────────────────────────
    if profile.languages:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("LANGUAGES", s["section"]))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=6))
        lang_str = "  •  ".join(f"{l.name} ({l.proficiency})" for l in profile.languages)
        story.append(Paragraph(lang_str, s["skill"]))

    doc.build(story)
    return buf.getvalue()
