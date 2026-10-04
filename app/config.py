from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "TutorFlow"
    database_url: str = "sqlite+aiosqlite:///./tutorflow.db"
    llm_provider: str = "mock"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"

    model_config = {"env_prefix": "TUTORFLOW_", "extra": "ignore"}


settings = Settings()
