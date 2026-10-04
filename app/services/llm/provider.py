from typing import Protocol


class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, user: str) -> str: ...


def get_provider():
    from app.config import settings

    if settings.llm_provider == "openai" and settings.llm_api_key:
        from app.services.llm.openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )

    from app.services.llm.mock import MockProvider

    return MockProvider()
