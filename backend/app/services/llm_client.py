"""LLM client routing for Ollama and optional cloud providers."""
import json
import re

import httpx

from app.core.config import settings
from app.schemas.document import LLMProvider


def _provider_name(provider: str | LLMProvider | None) -> str:
    if provider is None:
        return LLMProvider.OLLAMA.value
    return provider.value if isinstance(provider, LLMProvider) else provider


def resolve_model(provider: str | LLMProvider | None, model: str | None = None) -> str:
    provider = _provider_name(provider)
    if model:
        return model
    return {
        LLMProvider.OLLAMA.value: settings.MODEL_A,
        LLMProvider.OPENAI.value: settings.OPENAI_MODEL,
        LLMProvider.ANTHROPIC.value: settings.ANTHROPIC_MODEL,
        LLMProvider.GEMINI.value: settings.GEMINI_MODEL,
    }[provider]


def ensure_provider_configured(provider: str | LLMProvider) -> None:
    provider = _provider_name(provider)
    if provider == LLMProvider.OPENAI.value and not settings.OPENAI_API_KEY:
        raise ValueError("OpenAI is not configured. Set OPENAI_API_KEY in backend/.env.")
    if provider == LLMProvider.ANTHROPIC.value and not settings.ANTHROPIC_API_KEY:
        raise ValueError("Claude is not configured. Set ANTHROPIC_API_KEY in backend/.env.")
    if provider == LLMProvider.GEMINI.value and not settings.GEMINI_API_KEY:
        raise ValueError("Gemini is not configured. Set GEMINI_API_KEY in backend/.env.")


def get_gemini_key(inline_key: str | None = None) -> str | None:
    """Resolve the Gemini API key. Inline key takes precedence over env config."""
    return inline_key or settings.GEMINI_API_KEY


def _flatten_messages(messages: list[dict]) -> str:
    sections: list[str] = []
    role_labels = {"system": "System", "developer": "System", "user": "User", "assistant": "Assistant"}
    for msg in messages:
        role = role_labels.get(msg.get("role", "user"), "User")
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {"input_text", "text"}:
                    text_parts.append(str(item.get("text", "")))
                else:
                    text_parts.append(str(item))
            content = "\n".join(part for part in text_parts if part)
        sections.append(f"[{role}]\n{content}".strip())
    return "\n\n".join(part for part in sections if part).strip()


def _extract_openai_output(data: dict) -> str:
    output_parts: list[str] = []
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") in {"output_text", "text"}:
                text = block.get("text")
                if text:
                    output_parts.append(text)
    if output_parts:
        return "\n".join(output_parts).strip()
    raise ValueError("OpenAI response did not include text output")


def _extract_anthropic_output(data: dict) -> str:
    output_parts = [
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text" and block.get("text")
    ]
    if output_parts:
        return "\n".join(output_parts).strip()
    raise ValueError("Anthropic response did not include text output")


def _extract_gemini_output(data: dict) -> str:
    output_parts: list[str] = []
    for candidate in data.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                output_parts.append(text)
    if output_parts:
        return "\n".join(output_parts).strip()
    raise ValueError("Gemini response did not include text output")


async def chat(
    model: str | None,
    messages: list[dict],
    temperature: float = 0.2,
    provider: str = LLMProvider.OLLAMA,
    json_mode: bool = False,
    api_key: str | None = None,  # Inline key — takes precedence over env var; never logged
) -> str:
    """
    Send a chat request to the specified provider.
    api_key: if provided, overrides the env-configured key for this request.
    keep_alive=0 tells Ollama to unload the model from memory immediately
    after the response, so the next model loads into a clean slot.
    """
    provider = _provider_name(provider)
    model = resolve_model(provider, model)
    prompt = _flatten_messages(messages)

    if provider == LLMProvider.OLLAMA.value:
        url = f"{settings.OLLAMA_BASE_URL}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": 0,          # unload model right after this call
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    # Inline api_key takes precedence over environment variable
    effective_openai_key = api_key or settings.OPENAI_API_KEY
    effective_anthropic_key = api_key or settings.ANTHROPIC_API_KEY
    effective_gemini_key = api_key or settings.GEMINI_API_KEY

    # Only check env config when no inline key is provided
    if not api_key:
        ensure_provider_configured(provider)

    if provider == LLMProvider.OPENAI.value:
        payload: dict = {
            "model": model,
            "input": prompt,
        }
        if json_mode:
            payload["text"] = {"format": {"type": "json_object"}}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {effective_openai_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            return _extract_openai_output(resp.json())

    if provider == LLMProvider.ANTHROPIC.value:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": effective_anthropic_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 2048,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            return _extract_anthropic_output(resp.json())

    if provider == LLMProvider.GEMINI.value:
        generation_config: dict = {"temperature": temperature}
        if json_mode:
            generation_config["responseMimeType"] = "application/json"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": effective_gemini_key},
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": generation_config,
                },
            )
            resp.raise_for_status()
            return _extract_gemini_output(resp.json())

    raise ValueError(f"Unsupported provider: {provider}")


async def chat_json(
    model: str | None,
    messages: list[dict],
    temperature: float = 0.2,
    provider: str = LLMProvider.OLLAMA,
    api_key: str | None = None,  # Inline key — takes precedence over env var; never logged
) -> dict:
    """Send a chat request and parse the response as JSON."""
    text = (await chat(model, messages, temperature, provider=provider, json_mode=True, api_key=api_key)).strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract either a JSON object or array from the response
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
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
