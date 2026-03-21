from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OCR_MODEL: str = "deepseek-ocr"
    MODEL_A: str = "qwen3:8b"
    UPLOAD_DIR: str = "/tmp/taxdebate_uploads"
    SESSION_DIR: str = "/tmp/taxdebate_sessions"
    MAX_FILE_SIZE_MB: int = 20

    class Config:
        env_file = ".env"


settings = Settings()
