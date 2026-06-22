from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

import httpx

from app.core.config import settings
from app.models.jobs import JobPosting


class SearchProvider(Protocol):
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        ...


# ── Adzuna ────────────────────────────────────────────────────────────────────

class AdzunaProvider:
    _BASE = "https://api.adzuna.com/v1/api/jobs"

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        if not settings.adzuna_app_id or not settings.adzuna_api_key:
            raise RuntimeError(
                "ADZUNA_APP_ID and ADZUNA_API_KEY must be set when SEARCH_PROVIDER=adzuna. "
                "Register for free at https://developer.adzuna.com"
            )

        url = f"{self._BASE}/{settings.adzuna_country}/search/1"
        params = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_api_key,
            "results_per_page": min(max_results, 50),
            "what": query,
            "where": location,
            "content-type": "application/json",
        }

        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()

        return [self._to_posting(r) for r in resp.json().get("results", [])]

    @staticmethod
    def _to_posting(raw: dict) -> JobPosting:
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")
        salary = (
            f"€{int(salary_min):,} – €{int(salary_max):,}"
            if salary_min and salary_max
            else None
        )

        created_str = raw.get("created")
        posted_at = None
        if created_str:
            try:
                posted_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return JobPosting(
            id=uuid4(),
            title=raw.get("title", ""),
            company=raw.get("company", {}).get("display_name", "Unknown"),
            location=raw.get("location", {}).get("display_name", ""),
            description=raw.get("description", ""),
            url=raw.get("redirect_url", ""),
            source="adzuna",
            posted_at=posted_at,
            salary_range=salary,
            employment_type=raw.get("contract_type"),
        )


# ── Mock (development / testing) ──────────────────────────────────────────────

_MOCK_JOBS = [
    {
        "title": "Senior Backend Engineer (Python)",
        "company": "FinTech GmbH",
        "location": "Munich, Germany",
        "description": (
            "We are looking for a Senior Backend Engineer to join our platform team. "
            "You will design and implement high-performance REST APIs using Python and FastAPI. "
            "Strong experience with PostgreSQL, Redis, Docker, and CI/CD pipelines is required. "
            "Experience with LLM integrations or AI pipelines is a strong plus."
        ),
        "url": "https://example.com/jobs/1",
        "salary_range": "€70,000 – €95,000",
        "employment_type": "permanent",
    },
    {
        "title": "ML Engineer – NLP / LLM",
        "company": "AI Startup AG",
        "location": "Munich, Germany (Hybrid)",
        "description": (
            "Join our NLP team to build production LLM pipelines using LangChain and Python. "
            "You will work on RAG systems, prompt engineering, and model evaluation. "
            "Requirements: Python 3.10+, experience with OpenAI or Anthropic APIs, "
            "Pydantic, FastAPI, vector databases (Qdrant or Weaviate)."
        ),
        "url": "https://example.com/jobs/2",
        "salary_range": "€80,000 – €110,000",
        "employment_type": "permanent",
    },
    {
        "title": "Full Stack Developer – React & Python",
        "company": "SaaS Corp",
        "location": "Munich, Germany",
        "description": (
            "We need a Full Stack Developer comfortable with React (TypeScript) on the frontend "
            "and Python (FastAPI or Django) on the backend. "
            "You will own features end-to-end, from database design to UI components. "
            "Experience with REST APIs, PostgreSQL, and modern testing practices required."
        ),
        "url": "https://example.com/jobs/3",
        "salary_range": "€65,000 – €85,000",
        "employment_type": "permanent",
    },
    {
        "title": "DevOps / Platform Engineer",
        "company": "Enterprise AG",
        "location": "Munich, Germany",
        "description": (
            "Looking for a DevOps Engineer to manage our Kubernetes clusters and CI/CD pipelines. "
            "Responsibilities include infrastructure-as-code with Terraform, "
            "monitoring with Prometheus/Grafana, and container orchestration with Docker and K8s. "
            "Python scripting skills are a plus."
        ),
        "url": "https://example.com/jobs/4",
        "salary_range": "€75,000 – €100,000",
        "employment_type": "permanent",
    },
    {
        "title": "Junior Python Developer",
        "company": "Consultancy GmbH",
        "location": "Munich, Germany",
        "description": (
            "Entry-level Python developer position. "
            "You will work on internal tooling, data pipelines, and API integrations. "
            "Knowledge of Python basics, Git, and REST APIs required. "
            "Mentorship and growth opportunities provided."
        ),
        "url": "https://example.com/jobs/5",
        "salary_range": "€40,000 – €52,000",
        "employment_type": "permanent",
    },
]


class MockProvider:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        return [
            JobPosting(
                id=uuid4(),
                source="mock",
                posted_at=datetime.now(tz=timezone.utc),
                **job,
            )
            for job in _MOCK_JOBS[:max_results]
        ]


# ── Factory ───────────────────────────────────────────────────────────────────

def get_search_provider() -> SearchProvider:
    if settings.search_provider == "adzuna":
        return AdzunaProvider()
    return MockProvider()
