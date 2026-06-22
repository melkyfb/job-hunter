from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import httpx

from app.core.config import settings
from app.models.jobs import JobPosting


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
