from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import LLMProvider, settings

router = APIRouter(prefix="/config", tags=["system"])


class LLMConfigView(BaseModel):
    provider: LLMProvider
    model: str
    base_url: str | None
    temperature: float
    max_retries: int
    api_key_set: bool


@router.get(
    "/llm",
    response_model=LLMConfigView,
    summary="Show the active LLM configuration (never exposes the API key)",
)
async def get_llm_config() -> LLMConfigView:
    return LLMConfigView(
        provider=settings.llm_provider,
        model=settings.active_model,
        base_url=settings.active_base_url,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        api_key_set=bool(settings.active_api_key),
    )
