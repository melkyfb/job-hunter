from __future__ import annotations

from textwrap import dedent

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting
from app.models.profile import ProfileMaster


def _build_xyz_evidence(profile: ProfileMaster) -> str:
    lines = []
    for exp in profile.work_experiences:
        for ach in exp.achievements:
            lines.append(f"- [{exp.company} / {exp.role}] {ach.as_bullet}")
    return "\n".join(lines) if lines else "No specific achievements listed."


_SYSTEM_PROMPT = dedent("""
    You are an expert career coach who writes compelling, concise cover letters.
    You write in a professional but human tone — not robotic, not sycophantic.
    Cover letters you write are specific, evidence-based, and never generic.
    Never say "I am writing to apply for" or "I am a passionate professional".
""").strip()


def generate_cover_letter(profile: ProfileMaster, job: JobPosting) -> str:
    """
    Chain-of-Thought cover letter generation.

    Step 1: Identify the core problem/need in the job description.
    Step 2: Select the 2-3 strongest XYZ achievements that solve that problem.
    Step 3: Write the cover letter using those achievements as evidence.

    The CoT reasoning is done internally (not exposed to the user) by asking the
    model to think step-by-step before writing, using a two-turn conversation.
    """
    client = get_llm_client()
    c = profile.contact
    xyz_evidence = _build_xyz_evidence(profile)

    # Turn 1 — CoT reasoning: analyze the job and select the best evidence
    reasoning_prompt = dedent(f"""
        I need to write a cover letter for this candidate applying to this job.

        CANDIDATE: {c.full_name}
        CANDIDATE'S XYZ ACHIEVEMENTS:
        {xyz_evidence}

        JOB TITLE: {job.title}
        COMPANY: {job.company}
        JOB DESCRIPTION:
        {job.description}

        Before writing the letter, reason through these steps:
        1. What is the core problem or need this company is trying to solve with this hire?
        2. Which 2-3 of the candidate's XYZ achievements most directly address that need?
        3. What unique angle makes this candidate stand out for this specific role?

        Write your reasoning clearly, then end with: "READY TO WRITE"
    """).strip()

    reasoning_response = client.chat.completions.create(
        model=settings.active_model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": reasoning_prompt},
        ],
    )
    reasoning = reasoning_response.choices[0].message.content or ""

    # Turn 2 — Write the letter using the reasoning as context
    writing_prompt = dedent(f"""
        Based on your analysis above, write the cover letter now.

        Requirements:
        - 3 paragraphs, maximum 250 words total
        - Opening: hook that shows you understand their specific problem (no generic openers)
        - Middle: 2 concrete XYZ achievements as evidence, with the metrics
        - Closing: one sentence on fit + clear call to action
        - Sign off with the candidate's name: {c.full_name}
        - Do NOT include date, address headers, or "Dear Hiring Manager" boilerplate
          unless the company name is known — if it is, use "Dear [Company] team,"

        Write only the letter text. No commentary.
    """).strip()

    letter_response = client.chat.completions.create(
        model=settings.active_model,
        temperature=0.4,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": reasoning_prompt},
            {"role": "assistant", "content": reasoning},
            {"role": "user", "content": writing_prompt},
        ],
    )

    return letter_response.choices[0].message.content or ""
