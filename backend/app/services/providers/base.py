from __future__ import annotations

from typing import Protocol

from app.models.jobs import JobPosting


class SearchProvider(Protocol):
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        ...
