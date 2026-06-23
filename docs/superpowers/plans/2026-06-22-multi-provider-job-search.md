# Multi-Provider Job Search — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-provider job search (Adzuna/Mock) with a parallel fan-out system supporting LinkedIn, Indeed, Google Jobs, Stepstone, and Xing, with per-provider toggle in `AutoSearchConfig`.

**Architecture:** Existing `SearchProvider` Protocol and concrete providers move into a new `providers/` subpackage; a `MultiProvider` class runs all enabled providers concurrently via `ThreadPoolExecutor` and deduplicates results by URL; `run_pipeline` gains an optional `provider` parameter so the scheduler can inject a `MultiProvider`; `AutoSearchConfig` gains a `providers: list[str]` field surfaced as checkboxes in the frontend.

**Tech Stack:** Python 3.12, Pydantic v2, `python-jobspy`, Playwright sync API, `concurrent.futures.ThreadPoolExecutor`, React + TypeScript

## Global Constraints

- `from __future__ import annotations` at top of every new Python file
- Pydantic v2 — `model_validate_json()`, never `.dict()`
- Python tests run from `backend/` directory: `cd backend && python -m pytest tests/ -v`
- `python-jobspy` added to `backend/requirements.txt` (no version pin — latest stable)
- Playwright already in requirements; use `from playwright.sync_api import sync_playwright`
- All new provider files live in `backend/app/services/providers/`
- `job_search.py`, `job_pipeline.py`, `auto_search_scheduler.py` are modified — not replaced
- Existing tests in `backend/tests/test_services/` must keep passing
- `JobPosting.source` stores the provider name string (e.g. `"linkedin"`, `"stepstone"`)
- URL dedup in `MultiProvider` is case-sensitive exact match on `posting.url`
- Provider failure → log `WARNING`, return `[]` — never propagate exception out of `MultiProvider`
- `get_multi_provider([])` → falls back to `["mock"]`

---

## File Map

**Create:**
- `backend/app/services/providers/__init__.py` — re-exports all public symbols
- `backend/app/services/providers/base.py` — `SearchProvider` Protocol
- `backend/app/services/providers/adzuna.py` — `AdzunaProvider` (moved)
- `backend/app/services/providers/mock.py` — `MockProvider` (moved)
- `backend/app/services/providers/jobspy_prov.py` — `JobSpyProvider`
- `backend/app/services/providers/stepstone.py` — `StepstoneScraper` + `_stepstone_card_to_posting`
- `backend/app/services/providers/xing.py` — `XingScraper` + `_xing_card_to_posting`
- `backend/tests/test_services/test_providers.py` — all provider + MultiProvider tests

**Modify:**
- `backend/app/services/job_search.py` — add `MultiProvider`, `get_multi_provider()`; remove old classes (now in providers/)
- `backend/app/services/job_pipeline.py` — add optional `provider` param to `run_pipeline()`
- `backend/app/services/auto_search_scheduler.py` — pass `get_multi_provider(config.providers)` in `_run()`
- `backend/app/models/auto_search.py` — add `providers: list[str]` to `AutoSearchConfig`
- `backend/requirements.txt` — add `python-jobspy`
- `frontend/src/api/client.ts` — add `providers: string[]` to `AutoSearchConfig`
- `frontend/src/components/AutoSearchConfig.tsx` — add provider toggle checkboxes

---

## Task 1: Providers subpackage — scaffold + move Adzuna + Mock

**Files:**
- Create: `backend/app/services/providers/__init__.py`
- Create: `backend/app/services/providers/base.py`
- Create: `backend/app/services/providers/adzuna.py`
- Create: `backend/app/services/providers/mock.py`
- Modify: `backend/app/services/job_search.py`
- Test: `backend/tests/test_services/test_providers.py`

**Interfaces:**
- Produces: `SearchProvider` Protocol importable from `app.services.providers`
- Produces: `AdzunaProvider`, `MockProvider` importable from `app.services.providers`
- `job_search.py` re-exports same symbols so no other files break yet

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services/test_providers.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.jobs import JobPosting


def _make_posting(url: str = "https://example.com/job") -> JobPosting:
    return JobPosting(
        id=uuid4(),
        title="Python Dev",
        company="Acme",
        location="Munich",
        description="Great role",
        url=url,
        source="mock",
    )


# ── AdzunaProvider ────────────────────────────────────────────────────────────

def test_adzuna_provider_builds_correct_url():
    from app.services.providers.adzuna import AdzunaProvider
    provider = AdzunaProvider()
    assert hasattr(provider, "_BASE")
    assert "adzuna.com" in provider._BASE


def test_adzuna_provider_to_posting_maps_fields():
    from app.services.providers.adzuna import AdzunaProvider
    raw = {
        "title": "Backend Dev",
        "company": {"display_name": "TechCo"},
        "location": {"display_name": "Munich"},
        "description": "Great job",
        "redirect_url": "https://adzuna.com/jobs/1",
        "salary_min": 70000,
        "salary_max": 90000,
        "contract_type": "permanent",
        "created": "2026-06-22T10:00:00Z",
    }
    posting = AdzunaProvider._to_posting(raw)
    assert posting.title == "Backend Dev"
    assert posting.company == "TechCo"
    assert posting.source == "adzuna"
    assert "70,000" in posting.salary_range
    assert posting.employment_type == "permanent"


# ── MockProvider ──────────────────────────────────────────────────────────────

def test_mock_provider_returns_job_postings():
    from app.services.providers.mock import MockProvider
    provider = MockProvider()
    results = provider.search("python", "Munich", 3)
    assert len(results) == 3
    assert all(isinstance(r, JobPosting) for r in results)
    assert all(r.source == "mock" for r in results)


def test_mock_provider_respects_max_results():
    from app.services.providers.mock import MockProvider
    results = MockProvider().search("python", "Munich", 1)
    assert len(results) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: `ImportError: cannot import name 'AdzunaProvider' from 'app.services.providers.adzuna'`

- [ ] **Step 3: Create providers subpackage**

`backend/app/services/providers/base.py`:
```python
from __future__ import annotations

from typing import Protocol

from app.models.jobs import JobPosting


class SearchProvider(Protocol):
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        ...
```

`backend/app/services/providers/adzuna.py`:
```python
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
```

`backend/app/services/providers/mock.py`:
```python
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
```

`backend/app/services/providers/__init__.py`:
```python
from __future__ import annotations

from app.services.providers.base import SearchProvider
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.mock import MockProvider

__all__ = ["SearchProvider", "AdzunaProvider", "MockProvider"]
```

- [ ] **Step 4: Update `job_search.py` to import from providers/**

Replace the entire content of `backend/app/services/job_search.py` with:

```python
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from app.core.config import settings
from app.models.jobs import JobPosting
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.base import SearchProvider
from app.services.providers.mock import MockProvider

logger = logging.getLogger(__name__)

__all__ = ["SearchProvider", "MultiProvider", "get_search_provider", "get_multi_provider"]


class MultiProvider:
    """Runs multiple SearchProviders in parallel and deduplicates results by URL."""

    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        all_results: list[JobPosting] = []
        with ThreadPoolExecutor(max_workers=max(len(self._providers), 1)) as pool:
            futures = {
                pool.submit(p.search, query, location, max_results): p
                for p in self._providers
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    all_results.extend(future.result())
                except Exception as exc:
                    logger.warning(
                        "Provider %s failed: %s", type(provider).__name__, exc
                    )

        seen: set[str] = set()
        deduped: list[JobPosting] = []
        for posting in all_results:
            if posting.url and posting.url not in seen:
                seen.add(posting.url)
                deduped.append(posting)
        return deduped


_REGISTRY: dict[str, Callable[[], SearchProvider]] = {
    "adzuna": AdzunaProvider,
    "mock": MockProvider,
}


def get_multi_provider(enabled: list[str]) -> MultiProvider:
    """Instantiate and return a MultiProvider for the given provider names."""
    names = enabled if enabled else ["mock"]
    providers: list[SearchProvider] = []
    for name in names:
        factory = _REGISTRY.get(name)
        if factory is None:
            logger.warning("Unknown provider '%s', skipping", name)
            continue
        try:
            providers.append(factory())
        except Exception as exc:
            logger.error("Failed to instantiate provider '%s': %s", name, exc)
    if not providers:
        providers = [MockProvider()]
    return MultiProvider(providers)


def get_search_provider() -> SearchProvider:
    """Backwards-compat shim — returns single provider based on settings."""
    if settings.search_provider == "adzuna":
        return AdzunaProvider()
    return MockProvider()
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: Verify existing tests still pass**

```
cd backend && python -m pytest tests/ -v
```
Expected: all previously passing tests still PASS

- [ ] **Step 7: Commit**

```
git add backend/app/services/providers/ backend/app/services/job_search.py backend/tests/test_services/test_providers.py
git commit -m "refactor: extract SearchProvider/AdzunaProvider/MockProvider into providers/ subpackage"
```

---

## Task 2: MultiProvider tests + `run_pipeline` provider param

**Files:**
- Modify: `backend/tests/test_services/test_providers.py` (add MultiProvider tests)
- Modify: `backend/app/services/job_pipeline.py` (add optional `provider` param)

**Interfaces:**
- Consumes: `MultiProvider`, `get_multi_provider()` from `app.services.job_search` (Task 1)
- Produces: `run_pipeline(..., provider: SearchProvider | None = None)` — used by Task 6

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_services/test_providers.py`:

```python
# ── MultiProvider ─────────────────────────────────────────────────────────────

from unittest.mock import Mock


def test_multi_provider_merges_results_from_all_providers():
    from app.services.job_search import MultiProvider

    p1 = Mock()
    p1.search.return_value = [_make_posting("https://site-a.com/1")]
    p2 = Mock()
    p2.search.return_value = [_make_posting("https://site-b.com/1")]

    multi = MultiProvider([p1, p2])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 2
    urls = {r.url for r in results}
    assert "https://site-a.com/1" in urls
    assert "https://site-b.com/1" in urls


def test_multi_provider_deduplicates_by_url():
    from app.services.job_search import MultiProvider

    same_url = "https://same.com/job/1"
    p1 = Mock()
    p1.search.return_value = [_make_posting(same_url)]
    p2 = Mock()
    p2.search.return_value = [_make_posting(same_url)]

    multi = MultiProvider([p1, p2])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].url == same_url


def test_multi_provider_continues_when_one_provider_fails():
    from app.services.job_search import MultiProvider

    bad = Mock()
    bad.search.side_effect = RuntimeError("rate limited")
    good = Mock()
    good.search.return_value = [_make_posting("https://good.com/job/1")]

    multi = MultiProvider([bad, good])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].url == "https://good.com/job/1"


def test_get_multi_provider_falls_back_to_mock_when_empty():
    from app.services.job_search import get_multi_provider
    from app.services.providers.mock import MockProvider

    multi = get_multi_provider([])
    # Should still be usable — delegate to MockProvider
    results = multi.search("python", "Munich", 2)
    assert len(results) == 2


def test_get_multi_provider_skips_unknown_names():
    from app.services.job_search import get_multi_provider

    # Should not raise — unknown name is skipped
    multi = get_multi_provider(["nonexistent_provider", "mock"])
    results = multi.search("python", "Munich", 1)
    assert len(results) >= 1


# ── run_pipeline provider param ───────────────────────────────────────────────

def test_run_pipeline_uses_injected_provider():
    from unittest.mock import patch
    from app.models.profile import ProfileMaster, ContactInfo
    from app.services.job_pipeline import run_pipeline

    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))
    mock_provider = Mock()
    mock_provider.search.return_value = []  # empty → pipeline returns []

    result = run_pipeline(profile, "python", "Munich", max_results=5, provider=mock_provider)

    mock_provider.search.assert_called_once_with("python", "Munich", 5)
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_providers.py::test_multi_provider_merges_results_from_all_providers tests/test_services/test_providers.py::test_run_pipeline_uses_injected_provider -v
```
Expected: FAIL — `MultiProvider` tests pass (already implemented in Task 1), `test_run_pipeline_uses_injected_provider` FAILS because `run_pipeline` doesn't accept `provider` param yet.

- [ ] **Step 3: Update `run_pipeline` to accept optional provider**

In `backend/app/services/job_pipeline.py`, change the import and function signature:

```python
# Replace:
from app.services.job_search import get_search_provider

# With:
from app.services.job_search import SearchProvider, get_search_provider
from typing import Optional
```

Change the `run_pipeline` signature and search step:

```python
def run_pipeline(
    profile: ProfileMaster,
    query: str,
    location: str,
    max_results: int = 20,
    progress_fn: Optional[ProgressFn] = None,
    provider: Optional[SearchProvider] = None,   # NEW — injected by scheduler
) -> list[RankedJob]:
    ...
    # Step 1 — Search
    _p("searching", f'Searching for "{query}" in {location}…', 10)
    _provider = provider if provider is not None else get_search_provider()
    postings: list[JobPosting] = _provider.search(query, location, max_results)
    ...
```

Leave all other code in `run_pipeline` unchanged.

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: 10 PASSED (5 from Task 1 + 5 new)

- [ ] **Step 5: Full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```
git add backend/tests/test_services/test_providers.py backend/app/services/job_pipeline.py
git commit -m "feat: MultiProvider fan-out with dedup + inject provider into run_pipeline"
```

---

## Task 3: JobSpyProvider (LinkedIn, Indeed, Google)

**Files:**
- Create: `backend/app/services/providers/jobspy_prov.py`
- Modify: `backend/app/services/providers/__init__.py`
- Modify: `backend/app/services/job_search.py` (add to `_REGISTRY`)
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_services/test_providers.py`

**Interfaces:**
- Consumes: `JobPosting` from `app.models.jobs`
- Produces: `JobSpyProvider(site_name: str)` — registered as `"linkedin"`, `"indeed"`, `"google"`

- [ ] **Step 1: Add dependency**

In `backend/requirements.txt`, add the line:
```
python-jobspy
```

Install it:
```
cd backend && pip install python-jobspy
```

- [ ] **Step 2: Write failing tests**

Append to `backend/tests/test_services/test_providers.py`:

```python
# ── JobSpyProvider ────────────────────────────────────────────────────────────

def test_jobspy_provider_maps_dataframe_row_to_posting():
    import pandas as pd
    from unittest.mock import patch
    from app.services.providers.jobspy_prov import JobSpyProvider

    mock_df = pd.DataFrame([{
        "title": "Python Engineer",
        "company": "TechCo GmbH",
        "location": "Munich, Germany",
        "description": "Build great things with Python",
        "job_url": "https://linkedin.com/jobs/123",
        "date_posted": None,
        "min_amount": 70000.0,
        "max_amount": 90000.0,
        "currency": "EUR",
        "job_type": "fulltime",
    }])

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=mock_df):
        results = JobSpyProvider("linkedin").search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].title == "Python Engineer"
    assert results[0].company == "TechCo GmbH"
    assert results[0].source == "linkedin"
    assert results[0].url == "https://linkedin.com/jobs/123"
    assert "70" in results[0].salary_range
    assert results[0].employment_type == "fulltime"


def test_jobspy_provider_returns_empty_on_empty_dataframe():
    import pandas as pd
    from unittest.mock import patch
    from app.services.providers.jobspy_prov import JobSpyProvider

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=pd.DataFrame()):
        results = JobSpyProvider("indeed").search("python", "Munich", 5)

    assert results == []


def test_jobspy_provider_calls_scrape_jobs_with_correct_args():
    import pandas as pd
    from unittest.mock import patch, call
    from app.services.providers.jobspy_prov import JobSpyProvider

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=pd.DataFrame()) as mock_scrape:
        JobSpyProvider("google").search("python developer", "Munich", 10)

    mock_scrape.assert_called_once_with(
        site_name=["google"],
        search_term="python developer",
        location="Munich",
        results_wanted=10,
        hours_old=72,
        verbose=0,
    )
```

- [ ] **Step 3: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_providers.py::test_jobspy_provider_maps_dataframe_row_to_posting -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.providers.jobspy_prov'`

- [ ] **Step 4: Create `jobspy_prov.py`**

`backend/app/services/providers/jobspy_prov.py`:

```python
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

import pandas as pd
from jobspy import scrape_jobs

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)


class JobSpyProvider:
    """Wraps python-jobspy to scrape LinkedIn, Indeed, or Google Jobs."""

    def __init__(self, site_name: str) -> None:
        self.site_name = site_name  # "linkedin" | "indeed" | "google"

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
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
```

- [ ] **Step 5: Register in `__init__.py` and `_REGISTRY`**

Update `backend/app/services/providers/__init__.py`:
```python
from __future__ import annotations

from app.services.providers.base import SearchProvider
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.mock import MockProvider
from app.services.providers.jobspy_prov import JobSpyProvider

__all__ = ["SearchProvider", "AdzunaProvider", "MockProvider", "JobSpyProvider"]
```

In `backend/app/services/job_search.py`, add import and registry entries:
```python
from app.services.providers.jobspy_prov import JobSpyProvider
```

Update `_REGISTRY`:
```python
_REGISTRY: dict[str, Callable[[], SearchProvider]] = {
    "adzuna":    AdzunaProvider,
    "mock":      MockProvider,
    "linkedin":  lambda: JobSpyProvider("linkedin"),
    "indeed":    lambda: JobSpyProvider("indeed"),
    "google":    lambda: JobSpyProvider("google"),
}
```

- [ ] **Step 6: Run tests**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: 13 PASSED

- [ ] **Step 7: Commit**

```
git add backend/app/services/providers/jobspy_prov.py backend/app/services/providers/__init__.py backend/app/services/job_search.py backend/requirements.txt backend/tests/test_services/test_providers.py
git commit -m "feat: add JobSpyProvider for LinkedIn, Indeed, and Google Jobs via python-jobspy"
```

---

## Task 4: StepstoneScraper + XingScraper (Playwright)

**Files:**
- Create: `backend/app/services/providers/stepstone.py`
- Create: `backend/app/services/providers/xing.py`
- Modify: `backend/app/services/providers/__init__.py`
- Modify: `backend/app/services/job_search.py` (`_REGISTRY`)
- Test: `backend/tests/test_services/test_providers.py`

**Interfaces:**
- Produces: `StepstoneScraper`, `XingScraper` — both implement `SearchProvider` Protocol
- Produces: `_stepstone_card_to_posting(card)`, `_xing_card_to_posting(card)` — tested directly

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_services/test_providers.py`:

```python
# ── StepstoneScraper ──────────────────────────────────────────────────────────

def _make_text_el(text: str):
    el = Mock()
    el.inner_text.return_value = text
    return el


def _make_link_el(href: str):
    el = Mock()
    el.get_attribute.return_value = href
    return el


def test_stepstone_card_to_posting_maps_fields():
    from app.services.providers.stepstone import _stepstone_card_to_posting

    card = Mock()
    card.query_selector.side_effect = lambda sel: {
        '[data-at="job-item-title"]': _make_text_el("Python Engineer"),
        '[data-at="job-item-company-name"]': _make_text_el("TechCo GmbH"),
        '[data-at="job-item-location"]': _make_text_el("Munich, Germany"),
        'a[data-at="job-item-title"]': _make_link_el("/jobs/python-engineer-123"),
        'time[datetime]': None,
    }.get(sel)

    posting = _stepstone_card_to_posting(card)

    assert posting.title == "Python Engineer"
    assert posting.company == "TechCo GmbH"
    assert posting.location == "Munich, Germany"
    assert posting.source == "stepstone"
    assert posting.url == "https://www.stepstone.de/jobs/python-engineer-123"


def test_stepstone_card_to_posting_handles_absolute_url():
    from app.services.providers.stepstone import _stepstone_card_to_posting

    card = Mock()
    card.query_selector.side_effect = lambda sel: {
        '[data-at="job-item-title"]': _make_text_el("Dev"),
        '[data-at="job-item-company-name"]': _make_text_el("Co"),
        '[data-at="job-item-location"]': _make_text_el("Munich"),
        'a[data-at="job-item-title"]': _make_link_el("https://www.stepstone.de/jobs/abc-123"),
        'time[datetime]': None,
    }.get(sel)

    posting = _stepstone_card_to_posting(card)
    assert posting.url == "https://www.stepstone.de/jobs/abc-123"


# ── XingScraper ───────────────────────────────────────────────────────────────

def test_xing_card_to_posting_maps_fields():
    from app.services.providers.xing import _xing_card_to_posting

    card = Mock()
    card.query_selector.side_effect = lambda sel: {
        '[data-testid="job-listing-item-title"]': _make_text_el("Backend Dev"),
        '[data-testid="job-listing-item-company-name"]': _make_text_el("StartupAG"),
        '[data-testid="job-listing-item-location"]': _make_text_el("Munich"),
        'a[data-testid="job-listing-item-title-link"]': _make_link_el("https://www.xing.com/jobs/123"),
    }.get(sel)

    posting = _xing_card_to_posting(card)

    assert posting.title == "Backend Dev"
    assert posting.company == "StartupAG"
    assert posting.source == "xing"
    assert posting.url == "https://www.xing.com/jobs/123"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_providers.py::test_stepstone_card_to_posting_maps_fields tests/test_services/test_providers.py::test_xing_card_to_posting_maps_fields -v
```
Expected: `ModuleNotFoundError: No module named 'app.services.providers.stepstone'`

- [ ] **Step 3: Create `stepstone.py`**

`backend/app/services/providers/stepstone.py`:

```python
from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import quote_plus
from uuid import uuid4

from playwright.sync_api import sync_playwright

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)

_TIMEOUT = 30_000  # ms
_MAX_SCROLLS = 3
_SCROLL_WAIT = 1500  # ms


class StepstoneScraper:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        url = (
            f"https://www.stepstone.de/jobs/{quote_plus(query)}"
            f"?where={quote_plus(location)}"
        )
        results: list[JobPosting] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=_TIMEOUT)
                try:
                    page.click('[data-at="cookie-consent-accept-all"]', timeout=3000)
                except Exception:
                    pass

                for _ in range(_MAX_SCROLLS):
                    cards = page.query_selector_all('article[data-at="job-item"]')
                    if len(cards) >= max_results:
                        break
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(_SCROLL_WAIT)

                cards = page.query_selector_all('article[data-at="job-item"]')[:max_results]
                for card in cards:
                    try:
                        results.append(_stepstone_card_to_posting(card))
                    except Exception as exc:
                        logger.debug("Stepstone card parse error: %s", exc)
            finally:
                browser.close()

        return results


def _stepstone_card_to_posting(card) -> JobPosting:
    title_el = card.query_selector('[data-at="job-item-title"]')
    company_el = card.query_selector('[data-at="job-item-company-name"]')
    location_el = card.query_selector('[data-at="job-item-location"]')
    link_el = card.query_selector('a[data-at="job-item-title"]')
    time_el = card.query_selector('time[datetime]')

    title = title_el.inner_text().strip() if title_el else ""
    company = company_el.inner_text().strip() if company_el else ""
    loc = location_el.inner_text().strip() if location_el else ""

    url = ""
    if link_el:
        href = link_el.get_attribute("href") or ""
        url = href if href.startswith("http") else f"https://www.stepstone.de{href}"

    posted_at: datetime | None = None
    if time_el:
        dt_str = time_el.get_attribute("datetime")
        if dt_str:
            try:
                posted_at = datetime.fromisoformat(dt_str)
            except ValueError:
                pass

    return JobPosting(
        id=uuid4(),
        title=title,
        company=company,
        location=loc,
        description="",
        url=url,
        source="stepstone",
        posted_at=posted_at,
    )
```

- [ ] **Step 4: Create `xing.py`**

`backend/app/services/providers/xing.py`:

```python
from __future__ import annotations

import logging
from urllib.parse import quote_plus
from uuid import uuid4

from playwright.sync_api import sync_playwright

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)

_TIMEOUT = 30_000
_MAX_SCROLLS = 3
_SCROLL_WAIT = 1500


class XingScraper:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        url = (
            f"https://www.xing.com/jobs/search"
            f"?keywords={quote_plus(query)}&location={quote_plus(location)}"
        )
        results: list[JobPosting] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=_TIMEOUT)
                try:
                    page.click('[data-testid="cookie-consent-button-accept"]', timeout=3000)
                except Exception:
                    pass

                for _ in range(_MAX_SCROLLS):
                    cards = page.query_selector_all('[data-testid="job-listing-item"]')
                    if len(cards) >= max_results:
                        break
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(_SCROLL_WAIT)

                cards = page.query_selector_all('[data-testid="job-listing-item"]')[:max_results]
                for card in cards:
                    try:
                        results.append(_xing_card_to_posting(card))
                    except Exception as exc:
                        logger.debug("Xing card parse error: %s", exc)
            finally:
                browser.close()

        return results


def _xing_card_to_posting(card) -> JobPosting:
    title_el = card.query_selector('[data-testid="job-listing-item-title"]')
    company_el = card.query_selector('[data-testid="job-listing-item-company-name"]')
    location_el = card.query_selector('[data-testid="job-listing-item-location"]')
    link_el = card.query_selector('a[data-testid="job-listing-item-title-link"]')

    title = title_el.inner_text().strip() if title_el else ""
    company = company_el.inner_text().strip() if company_el else ""
    loc = location_el.inner_text().strip() if location_el else ""
    url = link_el.get_attribute("href") if link_el else ""

    return JobPosting(
        id=uuid4(),
        title=title,
        company=company,
        location=loc,
        description="",
        url=url or "",
        source="xing",
    )
```

- [ ] **Step 5: Register in `__init__.py` and `_REGISTRY`**

Update `backend/app/services/providers/__init__.py`:
```python
from __future__ import annotations

from app.services.providers.base import SearchProvider
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.mock import MockProvider
from app.services.providers.jobspy_prov import JobSpyProvider
from app.services.providers.stepstone import StepstoneScraper
from app.services.providers.xing import XingScraper

__all__ = [
    "SearchProvider",
    "AdzunaProvider",
    "MockProvider",
    "JobSpyProvider",
    "StepstoneScraper",
    "XingScraper",
]
```

In `backend/app/services/job_search.py`, add imports:
```python
from app.services.providers.stepstone import StepstoneScraper
from app.services.providers.xing import XingScraper
```

Update `_REGISTRY`:
```python
_REGISTRY: dict[str, Callable[[], SearchProvider]] = {
    "adzuna":    AdzunaProvider,
    "mock":      MockProvider,
    "linkedin":  lambda: JobSpyProvider("linkedin"),
    "indeed":    lambda: JobSpyProvider("indeed"),
    "google":    lambda: JobSpyProvider("google"),
    "stepstone": StepstoneScraper,
    "xing":      XingScraper,
}
```

- [ ] **Step 6: Run tests**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: 17 PASSED

- [ ] **Step 7: Commit**

```
git add backend/app/services/providers/stepstone.py backend/app/services/providers/xing.py backend/app/services/providers/__init__.py backend/app/services/job_search.py backend/tests/test_services/test_providers.py
git commit -m "feat: add StepstoneScraper and XingScraper via Playwright"
```

---

## Task 5: `AutoSearchConfig.providers` field + scheduler wiring

**Files:**
- Modify: `backend/app/models/auto_search.py`
- Modify: `backend/app/services/auto_search_scheduler.py`
- Test: `backend/tests/test_services/test_providers.py`

**Interfaces:**
- Consumes: `get_multi_provider(enabled: list[str])` from `app.services.job_search` (Task 1/3/4)
- Consumes: `run_pipeline(..., provider=...)` from `app.services.job_pipeline` (Task 2)
- Produces: `AutoSearchConfig.providers: list[str]` — default `["linkedin","indeed","google","stepstone","xing"]`

- [ ] **Step 1: Write failing test**

Append to `backend/tests/test_services/test_providers.py`:

```python
# ── AutoSearchConfig.providers ────────────────────────────────────────────────

def test_auto_search_config_providers_default():
    from app.models.auto_search import AutoSearchConfig

    config = AutoSearchConfig()
    assert "linkedin" in config.providers
    assert "indeed" in config.providers
    assert "google" in config.providers
    assert "stepstone" in config.providers
    assert "xing" in config.providers


def test_auto_search_config_providers_json_roundtrip():
    from app.models.auto_search import AutoSearchConfig

    config = AutoSearchConfig(providers=["linkedin", "stepstone"])
    json_str = config.model_dump_json()
    loaded = AutoSearchConfig.model_validate_json(json_str)
    assert loaded.providers == ["linkedin", "stepstone"]


def test_auto_search_config_without_providers_field_uses_default():
    """Old JSON files without 'providers' key should load with defaults."""
    import json
    from app.models.auto_search import AutoSearchConfig

    old_json = json.dumps({
        "enabled": True,
        "interval_hours": 2,
        "location": "Munich",
        "page_size": 10,
        "entries": [],
    })
    config = AutoSearchConfig.model_validate_json(old_json)
    assert len(config.providers) == 5
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && python -m pytest tests/test_services/test_providers.py::test_auto_search_config_providers_default -v
```
Expected: `FAIL — 'AutoSearchConfig' object has no attribute 'providers'`

- [ ] **Step 3: Add `providers` field to `AutoSearchConfig`**

In `backend/app/models/auto_search.py`, update `AutoSearchConfig`:

```python
class AutoSearchConfig(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=2, ge=1, le=168)
    location: str = "Munich, Germany"
    page_size: int = Field(default=10, ge=5, le=50)
    providers: list[str] = Field(
        default_factory=lambda: ["linkedin", "indeed", "google", "stepstone", "xing"]
    )
    entries: list[SearchEntry] = Field(default_factory=list)
```

- [ ] **Step 4: Update scheduler to use `get_multi_provider`**

In `backend/app/services/auto_search_scheduler.py`, update the import at the top of `_run()`:

```python
def _run() -> None:
    """Background thread body: run pipeline for each active entry and upsert results."""
    try:
        config = load_config()
        if not config.enabled or not config.entries:
            return

        from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
        from app.services.job_pipeline import run_pipeline
        from app.services.job_search import get_multi_provider   # NEW

        try:
            profile = ProfileRepository().load()
        except ProfileNotFoundError:
            logger.warning("Auto-search: no profile found, skipping run")
            return

        multi = get_multi_provider(config.providers)   # NEW — build once per run

        run_id = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        for entry in config.entries:
            if not entry.active:
                continue
            query = f"{entry.title} {' '.join(entry.keywords)}"
            try:
                results = run_pipeline(          # provider= injected
                    profile, query, config.location, max_results=20, provider=multi
                )
                new = upsert_jobs(results, run_id=run_id, found_via=entry.title)
                logger.info("Auto-search '%s': %d results, %d new", entry.title, len(results), new)
            except Exception as exc:
                logger.warning("Auto-search entry '%s' failed: %s", entry.title, exc)

        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=config.interval_hours)
        update_run_times(last_run_at=now, next_run_at=next_run)
    except Exception as exc:
        logger.error("Auto-search _run() error: %s", exc, exc_info=True)
```

- [ ] **Step 5: Run tests**

```
cd backend && python -m pytest tests/test_services/test_providers.py -v
```
Expected: 20 PASSED

- [ ] **Step 6: Full test suite**

```
cd backend && python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```
git add backend/app/models/auto_search.py backend/app/services/auto_search_scheduler.py backend/tests/test_services/test_providers.py
git commit -m "feat: AutoSearchConfig.providers field + scheduler uses get_multi_provider"
```

---

## Task 6: Frontend — provider toggles

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/AutoSearchConfig.tsx`

**Interfaces:**
- Consumes: `AutoSearchConfig.providers: list[str]` (Task 5)
- No new API endpoints — `PUT /auto-search/config` already persists the full config object

- [ ] **Step 1: Update `AutoSearchConfig` type in `client.ts`**

Find the `AutoSearchConfig` interface in `frontend/src/api/client.ts` and add the `providers` field:

```typescript
interface AutoSearchConfig {
  enabled: boolean
  interval_hours: number
  location: string
  page_size: number
  providers: string[]   // NEW
  entries: SearchEntry[]
}
```

- [ ] **Step 2: Add provider constants to `AutoSearchConfig.tsx`**

At the top of `frontend/src/components/AutoSearchConfig.tsx`, add after the imports:

```typescript
const ALL_PROVIDERS: { id: string; label: string }[] = [
  { id: 'linkedin',  label: 'LinkedIn'    },
  { id: 'indeed',    label: 'Indeed'      },
  { id: 'google',    label: 'Google Jobs' },
  { id: 'stepstone', label: 'Stepstone'   },
  { id: 'xing',      label: 'Xing'        },
]
```

- [ ] **Step 3: Add provider toggles to the component JSX**

Inside the expanded config form, after the `location` input field, add:

```tsx
{/* Providers */}
<div style={{ marginBottom: '12px' }}>
  <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-h)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
    Providers
  </label>
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
    {ALL_PROVIDERS.map(({ id, label }) => {
      const checked = (draft.providers ?? []).includes(id)
      return (
        <label key={id} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={checked}
            onChange={() => {
              const current = draft.providers ?? []
              const next = checked
                ? current.filter(p => p !== id)
                : [...current, id]
              setDraft(d => ({ ...d, providers: next }))
            }}
          />
          {label}
        </label>
      )
    })}
  </div>
</div>
```

**Note:** `draft` is the local state copy of `AutoSearchConfig`. If the component uses a different state variable name, adapt accordingly. The component pattern is: local `draft` state initialized from `config` prop, mutated on change, submitted via "Salvar" button calling `saveAutoSearchConfig(draft)`.

- [ ] **Step 4: Handle missing `providers` from old persisted config**

In the component's initialization (where `draft` is set from the `config` prop), ensure `providers` has a fallback:

```typescript
const [draft, setDraft] = useState<AutoSearchConfig>({
  ...config,
  providers: config.providers ?? ['linkedin', 'indeed', 'google', 'stepstone', 'xing'],
})
```

If the component already does `useState(config)` directly, add a `useEffect` to reset draft when `config` prop changes:

```typescript
useEffect(() => {
  setDraft({
    ...config,
    providers: config.providers ?? ['linkedin', 'indeed', 'google', 'stepstone', 'xing'],
  })
}, [config])
```

- [ ] **Step 5: TypeScript check**

```
cd frontend && npx tsc -b --noEmit
```
Expected: 0 errors

- [ ] **Step 6: Commit**

```
git add frontend/src/api/client.ts frontend/src/components/AutoSearchConfig.tsx
git commit -m "feat: provider toggle checkboxes in AutoSearchConfig panel"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| LinkedIn via python-jobspy | Task 3 |
| Indeed via python-jobspy | Task 3 |
| Google Jobs via python-jobspy | Task 3 |
| Stepstone via Playwright | Task 4 |
| Xing via Playwright | Task 4 |
| Adzuna kept | Task 1 (moved, not removed) |
| Mock kept | Task 1 (moved, not removed) |
| providers/ subpackage | Task 1 |
| `MultiProvider` fan-out via `ThreadPoolExecutor` | Task 1 |
| Dedup by URL | Task 1 |
| Per-provider error isolation (log + `[]`) | Task 1 + tests Task 2 |
| `get_multi_provider(enabled)` factory with `_REGISTRY` | Task 1 |
| `get_multi_provider([])` falls back to mock | Task 2 test |
| `run_pipeline` optional `provider` param | Task 2 |
| `python-jobspy` in requirements.txt | Task 3 |
| `AutoSearchConfig.providers: list[str]` | Task 5 |
| Default providers = all 5 | Task 5 |
| Old JSON without `providers` loads with default | Task 5 test |
| Scheduler uses `get_multi_provider(config.providers)` | Task 5 |
| `client.ts` `AutoSearchConfig` gains `providers: string[]` | Task 6 |
| Provider checkboxes in `AutoSearchConfig.tsx` | Task 6 |
| Playwright timeout 30s per scraper | Task 4 (\_TIMEOUT = 30\_000) |
| Stepstone selectors: `data-at="job-item-*"` | Task 4 |
| Xing selectors: `data-testid="job-listing-item-*"` | Task 4 |
| Cookie consent dismissed on Stepstone + Xing | Task 4 |
| `posting.source` stores provider name | All tasks |

All requirements covered. No placeholders. Type consistency verified: `SearchProvider` Protocol in `base.py`, imported via `providers/__init__.py` and `job_search.py`; `MultiProvider.search()` signature matches Protocol; `run_pipeline(provider=...)` matches `SearchProvider` type.
