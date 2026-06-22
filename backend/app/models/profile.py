from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.models.design import DesignVersion


class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class XYZExperience(BaseModel):
    """
    Enforces Google's XYZ resume formula:
    "Accomplished [X] as measured by [Y], by doing [Z]"
    """

    action: str = Field(
        description="What you accomplished (X). E.g.: 'Reduced API response time'"
    )
    metric: str = Field(
        description="How it was measured (Y). E.g.: 'by 40%, from 800ms to 480ms'"
    )
    context: str = Field(
        description="How you did it (Z). E.g.: 'by implementing Redis caching layer'"
    )

    @property
    def as_bullet(self) -> str:
        return f"{self.action} {self.metric} {self.context}"


class WorkExperience(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    company: str
    role: str
    start_date: date
    end_date: Optional[date] = None
    is_current: bool = False
    location: Optional[str] = None
    achievements: list[XYZExperience] = Field(
        min_length=1,
        description="At least one XYZ achievement required per role",
    )
    technologies: list[str] = Field(default_factory=list)
    raw_description: Optional[str] = Field(
        default=None,
        description="Original text from the resume — kept for LLM re-processing",
        exclude=True,
    )

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: Optional[date], info) -> Optional[date]:
        if v and info.data.get("start_date") and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class Education(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    institution: str
    degree: str
    field_of_study: str
    start_date: date
    end_date: Optional[date] = None
    grade: Optional[str] = None
    relevant_courses: list[str] = Field(default_factory=list)

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: Optional[date], info) -> Optional[date]:
        if v and info.data.get("start_date") and v < info.data["start_date"]:
            raise ValueError("end_date must be after start_date")
        return v


class Skill(BaseModel):
    name: str
    level: SkillLevel
    years_of_experience: Optional[float] = None


class Language(BaseModel):
    name: str
    proficiency: str = Field(description="E.g.: Native, C1, B2, Conversational")


class ContactInfo(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class JobSuggestion(BaseModel):
    """A job title + ATS keywords recommended for this profile."""

    title: str = Field(description="Job title to search for, e.g. 'Senior Backend Engineer'")
    keywords: list[str] = Field(
        description="3–5 ATS-relevant keywords for this title",
        min_length=1,
    )


class ProfileMaster(BaseModel):
    """
    Single Source of Truth (SSOT) for the candidate's profile.
    Persisted locally at .job_hunter/profile_master.json
    """

    id: UUID = Field(default_factory=uuid4)
    contact: ContactInfo
    summary: Optional[str] = Field(
        default=None,
        description="Professional summary — generated or provided by the user",
    )
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    job_suggestions: list[JobSuggestion] = Field(
        default_factory=list,
        description="Job titles + keywords generated from this profile during ingestion",
    )
    design_versions: list[DesignVersion] = Field(
        default_factory=list,
        description="Saved resume and cover letter HTML design templates",
    )
    active_resume_design_id: Optional[str] = Field(
        default=None,
        description="ID of the DesignVersion used by default for resume generation",
    )
    active_cover_letter_design_id: Optional[str] = Field(
        default=None,
        description="ID of the DesignVersion used by default for cover letter generation",
    )
