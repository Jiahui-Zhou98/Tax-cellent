from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OCR_MODEL: str = "deepseek-ocr"
    MODEL_A: str = "qwen3:8b"
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-5.2"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3-flash-preview"
    UPLOAD_DIR: str = "/tmp/taxdebate_uploads"
    SESSION_DIR: str = "/tmp/taxdebate_sessions"
    MAX_FILE_SIZE_MB: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
