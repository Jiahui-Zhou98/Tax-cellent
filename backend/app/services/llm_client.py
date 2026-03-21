"""Ollama LLM client — sequential, one model loaded at a time."""
import json
import re
import httpx
from app.core.config import settings


async def chat(model: str, messages: list[dict], temperature: float = 0.2) -> str:
    """
    Send a chat request to Ollama.
    keep_alive=0 tells Ollama to unload the model from memory immediately
    after the response, so the next model loads into a clean slot.
    """
    url = f"{settings.OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": 0,          # unload model right after this call
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def chat_json(model: str, messages: list[dict], temperature: float = 0.2) -> dict:
    """Send a chat request and parse the response as JSON."""
    text = (await chat(model, messages, temperature)).strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse JSON from model response: {text[:200]}")


async def check_ollama_available() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            return resp.status_code == 200
    except Exception:
        return False
