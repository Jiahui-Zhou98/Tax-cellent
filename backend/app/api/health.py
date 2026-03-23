from fastapi import APIRouter
from app.services.llm_client import check_ollama_available
from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    ollama_ok = await check_ollama_available()
    return {
        "status": "ok",
        "ollama": "available" if ollama_ok else "unavailable",
        "providers": {
            "ollama": {
                "configured": True,
                "running": ollama_ok,
            },
            "openai": {
                "configured": bool(settings.OPENAI_API_KEY),
            },
            "anthropic": {
                "configured": bool(settings.ANTHROPIC_API_KEY),
            },
            "gemini": {
                "configured": bool(settings.GEMINI_API_KEY),
            },
        },
    }
