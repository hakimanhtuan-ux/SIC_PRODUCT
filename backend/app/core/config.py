from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


def _is_real_key(val: str | None) -> bool:
    if not val:
        return False
    cleaned = val.strip()
    if not cleaned:
        return False
    placeholders = {
        "your_gemini_api_key_here",
        "your_google_factcheck_api_key_here",
        "your_tavily_api_key_here",
        "your_google_cse_api_key_here",
        "your_programmable_search_engine_id_here",
        "changeme",
    }
    return cleaned.lower() not in placeholders


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    PROJECT_NAME: str = "TrueCheck AI Verification Engine"
    VERSION: str = "0.1.0-mvp"

    # Gemini API (Google AI Studio Free Tier)
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.8-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    GEMINI_EMBEDDING_DIM: int = 768

    # Ollama Local AI (100% Free Local Open-Source LLM option)
    OLLAMA_ENABLED: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Search & Fact-Check APIs
    GOOGLE_FACTCHECK_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    GOOGLE_CSE_API_KEY: str = ""
    GOOGLE_CSE_CX: str = ""

    # Database & Cache
    DATABASE_URL: str = "postgresql+asyncpg://truecheck:truecheck_secret@localhost:5432/truecheck_db"
    ALLOW_SQLITE_FALLBACK: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Guardrails & Memory
    ENABLE_DEMO_FALLBACK: bool = True
    CLAIM_MEMORY_SIMILARITY_THRESHOLD: float = 0.90
    CLAIM_MEMORY_TTL_DAYS: int = 30
    DOCUMENT_RETENTION_HOURS: int = 24
    MAX_UPLOAD_SIZE_MB: int = 15

    # Server & CORS
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    STORAGE_DIR: Path = Path(__file__).resolve().parents[2] / "storage"

    @property
    def has_gemini_key(self) -> bool:
        return _is_real_key(self.GEMINI_API_KEY)

    @property
    def has_factcheck_key(self) -> bool:
        return _is_real_key(self.GOOGLE_FACTCHECK_API_KEY)

    @property
    def has_tavily_key(self) -> bool:
        return _is_real_key(self.TAVILY_API_KEY)

    @property
    def has_google_cse(self) -> bool:
        return _is_real_key(self.GOOGLE_CSE_API_KEY) and _is_real_key(self.GOOGLE_CSE_CX)

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip() and "*" not in o]


settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
(settings.STORAGE_DIR / "uploads").mkdir(parents=True, exist_ok=True)
(settings.STORAGE_DIR / "exports").mkdir(parents=True, exist_ok=True)

