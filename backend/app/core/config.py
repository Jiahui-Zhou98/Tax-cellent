from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OCR_MODEL: str = "deepseek-ocr"
    MODEL_A: str = "qwen3:8b"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.0-flash"
    UPLOAD_DIR: str = "/tmp/taxdebate_uploads"
    SESSION_DIR: str = "/tmp/taxdebate_sessions"
    MAX_FILE_SIZE_MB: int = 20
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_file = ".env"


settings = Settings()
