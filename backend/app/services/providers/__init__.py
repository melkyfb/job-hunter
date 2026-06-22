from __future__ import annotations

from app.services.providers.base import SearchProvider
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.mock import MockProvider

__all__ = ["SearchProvider", "AdzunaProvider", "MockProvider"]
