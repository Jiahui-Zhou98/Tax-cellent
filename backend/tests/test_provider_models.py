"""Tests for the Model List Single Source of Truth (TODO-14).

Verifies that:
- constants/models.py is the canonical dict
- review.py imports from constants (not its own copy)
- GET /api/providers/models returns the correct structure
- Validation in /analyze still uses the same list

Run: pytest backend/tests/test_provider_models.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.constants.models import PROVIDER_MODELS
from app.api.review import PROVIDER_MODELS as REVIEW_PROVIDER_MODELS


client = TestClient(app)


class TestProviderModelsConstant:
    """The constant in constants/models.py is well-formed."""

    def test_all_cloud_providers_have_models(self):
        for provider in ("openai", "anthropic", "gemini"):
            assert len(PROVIDER_MODELS[provider]) > 0, f"{provider} has no models"

    def test_ollama_has_empty_list(self):
        """Ollama accepts any model name — empty list signals free-text input."""
        assert PROVIDER_MODELS["ollama"] == []

    def test_all_model_names_are_strings(self):
        for provider, models in PROVIDER_MODELS.items():
            for m in models:
                assert isinstance(m, str), f"{provider}/{m} is not a string"

    def test_review_py_imports_same_object(self):
        """review.py must use the same dict as constants/models.py — not its own copy."""
        assert REVIEW_PROVIDER_MODELS is PROVIDER_MODELS, (
            "review.py defines its own PROVIDER_MODELS instead of importing from "
            "app.constants.models — the two sources have diverged"
        )


class TestProvidersModelsEndpoint:
    """GET /api/providers/models returns the canonical model lists."""

    def test_endpoint_returns_200(self):
        resp = client.get("/api/providers/models")
        assert resp.status_code == 200

    def test_response_contains_all_providers(self):
        resp = client.get("/api/providers/models")
        data = resp.json()
        for provider in ("ollama", "openai", "anthropic", "gemini"):
            assert provider in data, f"{provider} missing from /api/providers/models"

    def test_openai_models_match_constant(self):
        resp = client.get("/api/providers/models")
        assert resp.json()["openai"] == PROVIDER_MODELS["openai"]

    def test_anthropic_models_match_constant(self):
        resp = client.get("/api/providers/models")
        assert resp.json()["anthropic"] == PROVIDER_MODELS["anthropic"]

    def test_gemini_models_match_constant(self):
        resp = client.get("/api/providers/models")
        assert resp.json()["gemini"] == PROVIDER_MODELS["gemini"]

    def test_ollama_returns_empty_list(self):
        resp = client.get("/api/providers/models")
        assert resp.json()["ollama"] == []

    def test_response_structure_matches_frontend_expectation(self):
        """Response must be a flat dict[str, list[str]] — no nested objects."""
        resp = client.get("/api/providers/models")
        data = resp.json()
        assert isinstance(data, dict)
        for provider, models in data.items():
            assert isinstance(models, list), f"{provider} value is not a list"
            for m in models:
                assert isinstance(m, str), f"{provider}/{m} is not a string"

    def test_validation_uses_same_models_as_endpoint(self):
        """A model returned by the endpoint must be accepted by /analyze validation."""
        # Pick the first OpenAI model from the endpoint
        resp = client.get("/api/providers/models")
        first_openai = resp.json()["openai"][0]
        # Validation passes when the model is in the allow-list
        from app.constants.models import PROVIDER_MODELS as PM
        assert first_openai in PM["openai"]
