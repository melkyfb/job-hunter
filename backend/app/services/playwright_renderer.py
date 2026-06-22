from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined
from playwright.sync_api import sync_playwright

from app.models.profile import ProfileMaster


def build_jinja_context(profile: ProfileMaster) -> dict[str, Any]:
    """Converts ProfileMaster into plain-dict context safe for Jinja2 templates."""
    c = profile.contact
    return {
        "profile": {
            "contact": {
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone or "",
                "location": c.location or "",
                "linkedin_url": c.linkedin_url or "",
                "github_url": c.github_url or "",
            },
            "summary": profile.summary or "",
            "work_experiences": [
                {
                    "role": exp.role,
                    "company": exp.company,
                    "location": exp.location or "",
                    "start_date": exp.start_date.strftime("%b %Y"),
                    "end_date": "Present" if exp.is_current else (
                        exp.end_date.strftime("%b %Y") if exp.end_date else ""
                    ),
                    "is_current": exp.is_current,
                    "achievements": [ach.as_bullet for ach in exp.achievements],
                    "technologies": exp.technologies,
                }
                for exp in profile.work_experiences
            ],
            "skills": [
                {"name": sk.name, "level": sk.level.value}
                for sk in profile.skills
            ],
            "education": [
                {
                    "degree": edu.degree,
                    "field_of_study": edu.field_of_study,
                    "institution": edu.institution,
                    "end_year": edu.end_date.strftime("%Y") if edu.end_date else "Present",
                }
                for edu in profile.education
            ],
            "languages": [
                {"name": lang.name, "proficiency": lang.proficiency}
                for lang in profile.languages
            ],
        }
    }


def build_dummy_context() -> dict[str, Any]:
    """Minimal fake context for template validation without a real profile."""
    return {
        "profile": {
            "contact": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+49 123 456",
                "location": "Berlin, Germany",
                "linkedin_url": "linkedin.com/in/johndoe",
                "github_url": "github.com/johndoe",
            },
            "summary": "Senior software engineer with 8 years building scalable backends.",
            "work_experiences": [
                {
                    "role": "Senior Backend Engineer",
                    "company": "Acme Corp",
                    "location": "Berlin",
                    "start_date": "Jan 2021",
                    "end_date": "Present",
                    "is_current": True,
                    "achievements": [
                        "Reduced API latency by 40% from 800ms to 480ms by implementing Redis caching.",
                        "Increased test coverage from 42% to 87% by introducing pytest fixtures.",
                    ],
                    "technologies": ["Python", "FastAPI", "Redis", "PostgreSQL"],
                }
            ],
            "skills": [
                {"name": "Python", "level": "expert"},
                {"name": "FastAPI", "level": "advanced"},
            ],
            "education": [
                {
                    "degree": "BSc",
                    "field_of_study": "Computer Science",
                    "institution": "TU Berlin",
                    "end_year": "2016",
                }
            ],
            "languages": [
                {"name": "English", "proficiency": "C1"},
                {"name": "German", "proficiency": "B2"},
            ],
        }
    }


def build_dummy_cover_letter_context() -> dict[str, Any]:
    return {
        "profile": {
            "contact": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+49 123 456",
                "location": "Berlin, Germany",
            }
        },
        "letter_body": "Dear Acme team,\n\nI am excited to apply for the Senior Engineer role.\n\nSincerely,\nJohn Doe",
        "job": {"title": "Senior Engineer", "company": "Acme Corp"},
    }


def render_template_to_html(template: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 HTML template string with the given context dict."""
    env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
    t = env.from_string(template)
    return t.render(**context)


def render_cover_letter_template_to_html(
    template: str,
    letter_body: str,
    job_title: str,
    job_company: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str = "",
    contact_location: str = "",
) -> str:
    """Render a cover letter Jinja2 template with letter-specific context."""
    ctx = {
        "profile": {
            "contact": {
                "full_name": contact_name,
                "email": contact_email,
                "phone": contact_phone,
                "location": contact_location,
            }
        },
        "letter_body": letter_body,
        "job": {"title": job_title, "company": job_company},
    }
    return render_template_to_html(template, ctx)


def render_html_to_pdf(html: str) -> bytes:
    """Convert an HTML string to PDF bytes using Playwright + Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
    return pdf
