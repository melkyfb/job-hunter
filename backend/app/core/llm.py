from functools import lru_cache

from openai import OpenAI

from app.core.config import settings


@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    """
    Returns a single shared OpenAI client.

    LLM_PROVIDER=openai  → official api.openai.com (base_url=None)
    LLM_PROVIDER=local   → any OpenAI-compatible server (Ollama, LM Studio, vLLM, …)
                           configured via LOCAL_BASE_URL / LOCAL_API_KEY

    The OpenAI SDK handles both cases identically — only base_url differs.
    """
    return OpenAI(
        api_key=settings.active_api_key,
        base_url=settings.active_base_url,  # None → SDK default (api.openai.com)
        max_retries=0,  # Retries are handled by the Self-Correction Loop in IngestionService
    )
