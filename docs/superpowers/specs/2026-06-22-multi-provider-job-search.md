# Multi-Provider Job Search — Spec

**Date:** 2026-06-22
**Status:** Approved for implementation

---

## Overview

Replace the single-provider job search (Adzuna only) with a fan-out multi-provider system supporting LinkedIn, Indeed, Google Jobs, Stepstone, and Xing. All providers run in parallel per search query; results are deduplicated by URL before scoring.

---

## 1. Provider Matrix

| Provider | Implementation | Notes |
|---|---|---|
| `linkedin` | `python-jobspy` | Scrapes LinkedIn Jobs |
| `indeed` | `python-jobspy` | Scrapes Indeed |
| `google` | `python-jobspy` | Scrapes Google Jobs |
| `stepstone` | Playwright headless | German job board |
| `xing` | Playwright headless | German job board |
| `adzuna` | Adzuna REST API | Existing, kept |
| `mock` | Hardcoded data | Dev/testing only |

`python-jobspy` (PyPI: `python-jobspy`) handles LinkedIn/Indeed/Google — avoids maintaining three separate scrapers. Stepstone and Xing require Playwright because no public API or jobspy support exists.

---

## 2. File Structure

New subpackage `backend/app/services/providers/`:

```
backend/app/services/providers/
  __init__.py          # exports SearchProvider, all concrete classes
  base.py              # SearchProvider Protocol definition
  adzuna.py            # AdzunaProvider (moved from job_search.py)
  mock.py              # MockProvider (moved from job_search.py)
  jobspy_prov.py       # JobSpyProvider(site_name) — linkedin/indeed/google
  stepstone.py         # StepstoneScraper — Playwright
  xing.py              # XingScraper — Playwright
```

Modified files:
- `backend/app/services/job_search.py` — becomes `MultiProvider` + `get_multi_provider()` factory; imports providers from subpackage
- `backend/app/models/auto_search.py` — `AutoSearchConfig` gains `providers: list[str]`
- `backend/app/services/auto_search_scheduler.py` — passes `config.providers` to `get_multi_provider()`
- `backend/requirements.txt` — adds `python-jobspy`
- `frontend/src/api/client.ts` — `AutoSearchConfig` type gains `providers: string[]`
- `frontend/src/components/AutoSearchConfig.tsx` — provider toggle checkboxes

---

## 3. Interfaces

### `SearchProvider` Protocol (base.py)

```python
from typing import Protocol
from app.models.jobs import JobPosting

class SearchProvider(Protocol):
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]: ...
```

### `MultiProvider` (job_search.py)

```python
class MultiProvider:
    def __init__(self, providers: list[SearchProvider]) -> None: ...

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        """
        Runs all providers concurrently via ThreadPoolExecutor.
        Each provider is isolated in try/except — failure returns [].
        Results deduplicated by posting.url before return.
        max_results applied per-provider (not total), so total may be up to
        len(providers) * max_results before dedup.
        """
```

### Factory (job_search.py)

```python
_REGISTRY: dict[str, Callable[[], SearchProvider]] = {
    "adzuna":    lambda: AdzunaProvider(),
    "linkedin":  lambda: JobSpyProvider("linkedin"),
    "indeed":    lambda: JobSpyProvider("indeed"),
    "google":    lambda: JobSpyProvider("google"),
    "stepstone": lambda: StepstoneScraper(),
    "xing":      lambda: XingScraper(),
    "mock":      lambda: MockProvider(),
}

def get_multi_provider(enabled: list[str]) -> MultiProvider:
    """Returns MultiProvider with only the listed providers instantiated."""
```

---

## 4. Provider Implementations

### `JobSpyProvider` (jobspy_prov.py)

```python
from jobspy import scrape_jobs  # python-jobspy

class JobSpyProvider:
    def __init__(self, site_name: str) -> None:
        self.site_name = site_name  # "linkedin" | "indeed" | "google"

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        df = scrape_jobs(
            site_name=[self.site_name],
            search_term=query,
            location=location,
            results_wanted=max_results,
            hours_old=72,
            verbose=0,
        )
        return [_row_to_posting(row, source=self.site_name) for _, row in df.iterrows()]
```

DataFrame columns used: `title`, `company`, `location`, `description`, `job_url`, `date_posted`, `min_amount`/`max_amount`/`currency`, `job_type`.

### `StepstoneScraper` (stepstone.py)

Playwright sync API, wrapped via `run_in_executor` by the caller (MultiProvider).

```
URL: https://www.stepstone.de/jobs/{query_slug}?where={location_slug}
Selectors:
  cards:       article[data-at="job-item"]
  title:       [data-at="job-item-title"]
  company:     [data-at="job-item-company-name"]
  location:    [data-at="job-item-location"]
  link (href): [data-at="job-item-title"] → href
  posted:      time[datetime]
```

Max results: scroll until `len(cards) >= max_results` or no new cards load (max 3 scroll attempts). Timeout: 30s total.

### `XingScraper` (xing.py)

```
URL: https://www.xing.com/jobs/search?keywords={query}&location={location}
Selectors:
  cards:    [data-testid="job-listing-item"]
  title:    [data-testid="job-listing-item-title"]
  company:  [data-testid="job-listing-item-company-name"]
  location: [data-testid="job-listing-item-location"]
  link:     a[data-testid="job-listing-item-title-link"] → href
```

Same scroll/timeout strategy as Stepstone.

### `AdzunaProvider` + `MockProvider`

Unchanged logic, moved to `providers/adzuna.py` and `providers/mock.py`.

---

## 5. MultiProvider Fan-Out

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
    results: list[JobPosting] = []
    with ThreadPoolExecutor(max_workers=len(self._providers)) as pool:
        futures = {
            pool.submit(p.search, query, location, max_results): p
            for p in self._providers
        }
        for future in as_completed(futures):
            try:
                results.extend(future.result())
            except Exception as exc:
                provider = futures[future]
                logger.warning("Provider %s failed: %s", type(provider).__name__, exc)

    # Dedup by URL (preserve first-seen)
    seen: set[str] = set()
    deduped: list[JobPosting] = []
    for posting in results:
        if posting.url and posting.url not in seen:
            seen.add(posting.url)
            deduped.append(posting)
    return deduped
```

---

## 6. Config Changes

### `AutoSearchConfig` (auto_search.py)

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

Existing `auto_search_config.json` files without `providers` field load fine — Pydantic fills default.

### Scheduler (auto_search_scheduler.py)

```python
# _run() — replace get_search_provider() call:
multi = get_multi_provider(config.providers or ["mock"])
results = run_pipeline_with_provider(multi, profile, query, config.location, max_results=20)
```

`run_pipeline` in `job_pipeline.py` needs a `provider` parameter (or `get_multi_provider` replaces `get_search_provider` inside it).

---

## 7. Frontend Changes

### `client.ts`

```typescript
interface AutoSearchConfig {
  enabled: boolean
  interval_hours: number
  location: string
  page_size: number
  providers: string[]           // NEW
  entries: SearchEntry[]
}
```

### `AutoSearchConfig.tsx`

Add "Providers" section inside the existing collapsible panel, below the `location` field:

```
Providers
[✓] LinkedIn  [✓] Indeed  [✓] Google Jobs
[✓] Stepstone [✓] Xing
```

Each checkbox toggles the provider name in/out of `config.providers`. Save via existing "Salvar" button.

---

## 8. Dependency

```
# requirements.txt
python-jobspy>=0.1.0
```

Playwright already in requirements for `playwright_renderer.py`.

---

## 9. Error Handling

- **Provider fails** (network, rate limit, selector change): logged as WARNING, returns `[]`, other providers unaffected.
- **All providers fail**: `MultiProvider.search()` returns `[]`. `run_pipeline` returns `[]`. `upsert_jobs` stores nothing. No exception raised — scheduler continues to next entry.
- **jobspy import error** (package not installed): `JobSpyProvider.__init__` raises `ImportError` at factory time, caught by scheduler, logged as ERROR.
- **Playwright timeout**: 30s per Playwright provider. `asyncio.TimeoutError` caught in provider, returns `[]`.

---

## 10. Out of Scope

- Authentication / login flows for LinkedIn (jobspy uses public search only)
- Pagination beyond `results_wanted` cap per provider
- Per-provider rate limit tuning / backoff
- Proxy rotation
- Frontend display of which provider each job came from (though `posting.source` field stores it)
- Glassdoor, ZipRecruiter, or other providers (can be added later via `_REGISTRY`)
