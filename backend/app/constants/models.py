"""Single source of truth for per-provider model allow-lists.

Both the validation logic in review.py and the GET /api/providers/models
endpoint import from here. The frontend fetches the endpoint on mount so
that SettingsStep always shows exactly the models the backend will accept.

To add a new model: update the list here — backend validation and frontend
picker stay in sync automatically.

Ollama entry is empty: Ollama accepts any model name, so no allow-list is
applied; the frontend renders a free-text input instead of a dropdown.
"""

# Provider → ordered list of supported model IDs (empty = any model accepted)
PROVIDER_MODELS: dict[str, list[str]] = {
    "ollama": [],
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-5.2"],
    "anthropic": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5"],
    "gemini": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
}
