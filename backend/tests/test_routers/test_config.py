# backend/tests/test_routers/test_config.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings, LLMProvider


@pytest.fixture(autouse=True)
def restore_settings():
    """Restore mutated settings fields after each test."""
    saved = {
        "cv_language": settings.cv_language,
        "cl_language": settings.cl_language,
        "search_provider": settings.search_provider,
        "adzuna_app_id": settings.adzuna_app_id,
        "llm_provider": settings.llm_provider,
        "local_model": settings.local_model,
    }
    yield
    for k, v in saved.items():
        setattr(settings, k, v)


@pytest.mark.asyncio
async def test_get_llm_config_returns_current_settings():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "model" in data
    assert "api_key_set" in data


@pytest.mark.asyncio
async def test_update_config_changes_language():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/config/update", json={
            "llm_provider": "local",
            "llm_model": "llama3.2",
            "cv_language": "Deutsch",
            "cl_language": "Deutsch",
        })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert settings.cv_language == "Deutsch"
    assert settings.cl_language == "Deutsch"


@pytest.mark.asyncio
async def test_update_config_sets_search_provider():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/config/update", json={
            "llm_provider": "local",
            "llm_model": "llama3.2",
            "search_provider": "adzuna",
            "adzuna_app_id": "test_id",
            "adzuna_api_key": "test_key",
        })
    assert resp.status_code == 200
    assert settings.search_provider == "adzuna"
    assert settings.adzuna_app_id == "test_id"
