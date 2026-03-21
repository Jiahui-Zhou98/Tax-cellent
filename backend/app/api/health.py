from fastapi import APIRouter
from app.services.llm_client import check_ollama_available

router = APIRouter()


@router.get("/health")
async def health():
    ollama_ok = await check_ollama_available()
    return {
        "status": "ok",
        "ollama": "available" if ollama_ok else "unavailable",
    }
