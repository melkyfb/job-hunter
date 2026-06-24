# backend/app/routers/config.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.core.config import LLMProvider, settings

router = APIRouter(prefix="/config", tags=["system"])


class LLMConfigView(BaseModel):
    provider: LLMProvider
    model: str
    base_url: Optional[str]
    temperature: float
    max_retries: int
    api_key_set: bool


class ConfigUpdate(BaseModel):
    llm_provider: str = "local"
    llm_model: str = "llama3.2"
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_temperature: float = 0.0
    adzuna_app_id: Optional[str] = None
    adzuna_api_key: Optional[str] = None
    adzuna_country: str = "de"
    search_provider: str = "mock"
    cv_prompt: Optional[str] = None
    cl_prompt: Optional[str] = None
    cv_language: str = "English"
    cl_language: str = "English"


@router.get("/llm", response_model=LLMConfigView)
async def get_llm_config() -> LLMConfigView:
    return LLMConfigView(
        provider=settings.llm_provider,
        model=settings.active_model,
        base_url=settings.active_base_url,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        api_key_set=bool(settings.active_api_key),
    )


@router.post("/update", status_code=200)
async def update_config(body: ConfigUpdate) -> dict:
    settings.update_from_config(
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
        llm_api_key=body.llm_api_key,
        llm_base_url=body.llm_base_url,
        llm_temperature=body.llm_temperature,
        adzuna_app_id=body.adzuna_app_id,
        adzuna_api_key=body.adzuna_api_key,
        adzuna_country=body.adzuna_country,
        search_provider=body.search_provider,
        cv_prompt=body.cv_prompt,
        cl_prompt=body.cl_prompt,
        cv_language=body.cv_language,
        cl_language=body.cl_language,
    )
    return {"ok": True}
