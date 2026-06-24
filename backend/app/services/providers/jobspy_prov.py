from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)


class JobSpyProvider:
    """Wraps python-jobspy to scrape LinkedIn, Indeed, or Google Jobs."""

    def __init__(self, site_name: str) -> None:
        self.site_name = site_name  # "linkedin" | "indeed" | "google"

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        # Lazy import — jobspy pulls in pandas/torch/scipy which bloat PyInstaller analysis
        import pandas as pd  # noqa: PLC0415
        from jobspy import scrape_jobs  # noqa: PLC0415

        df: pd.DataFrame = scrape_jobs(
            site_name=[self.site_name],
            search_term=query,
            location=location,
            results_wanted=max_results,
            hours_old=72,
            verbose=0,
        )
        if df.empty:
            return []
        return [_row_to_posting(row, source=self.site_name) for _, row in df.iterrows()]


def _row_to_posting(row: Any, source: str) -> JobPosting:
    import pandas as pd  # noqa: PLC0415

    salary: str | None = None
    min_amt = row.get("min_amount")
    max_amt = row.get("max_amount")
    if pd.notna(min_amt) and pd.notna(max_amt):
        curr = row.get("currency") or "€"
        salary = f"{curr}{int(min_amt):,} – {curr}{int(max_amt):,}"

    posted_at: datetime | None = None
    dp = row.get("date_posted")
    if dp is not None and pd.notna(dp):
        if isinstance(dp, datetime):
            posted_at = dp if dp.tzinfo else dp.replace(tzinfo=timezone.utc)
        elif isinstance(dp, date):
            posted_at = datetime(dp.year, dp.month, dp.day, tzinfo=timezone.utc)

    job_type = row.get("job_type")

    return JobPosting(
        id=uuid4(),
        title=str(row.get("title") or ""),
        company=str(row.get("company") or "Unknown"),
        location=str(row.get("location") or ""),
        description=str(row.get("description") or ""),
        url=str(row.get("job_url") or ""),
        source=source,
        posted_at=posted_at,
        salary_range=salary,
        employment_type=str(job_type) if job_type and pd.notna(job_type) else None,
    )
