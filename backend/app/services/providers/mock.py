from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.models.jobs import JobPosting


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
