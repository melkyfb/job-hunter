from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.design import DesignVersion
from app.services.design_generator import generate_resume_template

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES: list[tuple[str, str]] = [
    (
        "1. Professional Equilibrium",
        "Two-column layout: left sidebar (30% width) in slate grey (#2d3748) with name, contact info, skills, and languages in white text. Right column (70%) on white with work experience using blue (#4299e1) timeline dots. Section headings in uppercase tracked letters. Arial 10pt throughout. Clean, balanced, and corporate-modern. Include: @page { size: A4; margin: 0; } in CSS.",
    ),
    (
        "2. Editorial Design",
        "Magazine-inspired single-column layout. Name as display type (Georgia 34pt) top-left. Contact details in a thin full-width horizontal rule band below. Body uses a two-column grid: experience descriptions left, dates right. Bold sans-serif section titles. Black and white with one accent in deep burgundy (#7c2d2d) for section titles and rules. Print-ready A4.",
    ),
    (
        "3. Techno Minimalism",
        "Dark terminal theme: #0d1117 background, #c9d1d9 body text. Monospace font (Courier New) throughout. Name in terminal green (#3fb950) top-left. Work experience bullets prefixed with › symbol. Skills displayed as inline code tags with subtle borders. Section dividers as horizontal rules in #30363d. Dates in muted grey. Developer aesthetic, A4 size.",
    ),
    (
        "4. Interface Aesthetic",
        "Clean UI-card design. Full-width top bar with name in white on light blue (#1d4ed8) background. Each work experience in a card with 1px border (#e5e7eb) and 4px border-radius. Skills as rounded pill badges. Section labels in small uppercase tracking on the left margin. Segoe UI 11pt. White background with subtle card shadows. A4 layout.",
    ),
    (
        "5. Swiss Style",
        "International Typographic Style: mathematical grid precision. Arial/Helvetica throughout with strict typographic hierarchy. Red (#dc2626) for section numbers (01, 02, 03) in large type. Name in bold 26pt top-left. Thin horizontal rules between sections. Experience in a strict three-column grid: date | role/company | bullet achievements. Minimal decoration. A4.",
    ),
    (
        "6. Fancy Dark Mode",
        "Premium dark layout: #1a1a2e background, #e8e8e8 body text. Gold (#c9a84c) accent for name (Georgia 28pt centered), section headings with left gold border rule, and skill badge outlines. Work experience bullets with diamond (◆) markers. Skills in gold-outline pill badges. Elegant and luxury-feel. White dividers at 10% opacity. A4 size.",
    ),
    (
        "7. Classic Modernism",
        "Mid-century modern: clean white with warm beige (#f5f0e8) left sidebar (28% width). Name in bold Verdana 22pt in sidebar. Sidebar contains contact, skills, education, languages. Main area: work experience in clean rows, italic company names, dates right-aligned. Section headings with thick terracotta (#c1440e) left border. Structured and timeless. A4.",
    ),
    (
        "8. Gently Neobrutalism",
        "Bold neobrutalist style: white background, 3px solid black borders around all section blocks. Name in bold Arial 30pt with bright yellow (#facc15) background header strip. Section headings on black background with white text, all caps. High contrast throughout. Dates in pill badges with black border. Intentionally strong visual weight. A4 layout.",
    ),
    (
        "9. Inclusive Design",
        "Accessibility-first high-contrast design. Pure white background, pure black text, minimum 13pt everywhere. Name in 24pt bold, clearly left-aligned. All sections in large readable blocks with clear headings. No decorative elements. Visual hierarchy through size and weight alone — no color distinctions for meaning. One blue (#0000EE) accent for links only. WCAG AAA. Two-column (65/35). A4.",
    ),
    (
        "10. Dynamic Monocolor",
        "Single-hue depth: deep navy (#003366) used at 5 opacity levels. Name/header: 100% navy, white text. Section headings: 80% navy background, white text. Alternating content rows: white and 6% navy tint. Borders at 20% navy. Accent timeline dots at 70% navy. Cohesive, professional, and unified by one color family. Arial 10pt. A4.",
    ),
    (
        "11. The Time of Experience",
        "Timeline-centric layout. Full left column (25% width) is a vertical timeline: years in circles connected by a vertical line in blue (#1565c0). Each work experience block floats right with a horizontal connector line. Education and skills in a compact two-column section at the bottom. Light grey (#f8f9fa) overall background. A4 size, print-ready.",
    ),
    (
        "12. The Lines of Evolution",
        "Geometric line-based design. Name in bold 26pt with a bold diagonal decorative separator below it. Section items separated by thin horizontal rules. Skills displayed as horizontal bar graphs (CSS only, no JS) showing proficiency. Progress lines for language levels. Black, white, and teal (#0d9488). Clean and data-driven aesthetic. A4 layout.",
    ),
    (
        "13. Future Now",
        "Modern sci-fi aesthetic without gimmicks. Name in letter-spacing: 6px, all caps, 20pt. Header in deep dark purple (#1e1b4b) gradient to black. Content in clean white with 1px #6c63ff left border on each section. Section labels in purple, uppercase tracking. Skills with rectangular outline badges in purple. Segoe UI Light throughout. A4.",
    ),
    (
        "14. Charm of Last Century",
        "Art Deco inspired. Warm champagne (#fef3c7) background with deep brown (#3d2b1f) text. Name centered in 26pt Georgia with ornamental horizontal rules above and below (using CSS border patterns). Section headings centered with flanking dash rules. Geometric corner ornament (CSS only) on the outer page border. Elegant and vintage. A4 size.",
    ),
    (
        "15. Journalism is Now",
        "Newspaper broadsheet layout. Name as a masthead in bold 28pt with full-width border below. Two-column body layout for experience descriptions (CSS columns). Dates styled as bylines in italic grey. Skills section formatted as a two-column classified-ad grid. Section headings as newspaper-style headlines with bold rules above. Black and white, high contrast. A4.",
    ),
]


def seed_default_designs(
    progress_fn: Callable[[int, int], None] | None = None,
) -> list[DesignVersion]:
    """
    Generate all 15 default resume templates in parallel.
    Individual failures are logged and skipped — never propagated.
    Returns templates in definition order.
    First element has is_default=True; caller must set active_resume_design_id.
    progress_fn(completed, total) called after each template finishes.
    """
    total = len(DEFAULT_TEMPLATES)
    ordered: dict[int, DesignVersion | None] = {}
    completed_count = 0

    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = {
            pool.submit(_generate_one, name, prompt): idx
            for idx, (name, prompt) in enumerate(DEFAULT_TEMPLATES)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ordered[idx] = future.result()
            except Exception as exc:
                logger.warning("Default template index %d failed: %s", idx, exc)
                ordered[idx] = None
            completed_count += 1
            if progress_fn:
                progress_fn(completed_count, total)

    results = [v for i in sorted(ordered) if (v := ordered[i]) is not None]
    if results:
        results[0].is_default = True
    return results


def _generate_one(name: str, prompt: str) -> DesignVersion:
    html_template = generate_resume_template(prompt, skip_intent_check=True)
    return DesignVersion(name=name, prompt=prompt, type="resume", html_template=html_template)
