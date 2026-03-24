"""Tests for cloud API provider feature — api_key threading, model validation,
authentication error handling, and health endpoint provider status.

These tests require no live LLM. All HTTP calls to cloud providers are mocked.

Run: pytest backend/tests/test_cloud_api.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.schemas.document import (
    AnalysisPreferences,
    ConfirmedFields,
    FieldValue,
    LLMProvider,
    SessionState,
    TaxReport,
    ValidationOutput,
)
from app.services.llm_client import ensure_provider_configured, resolve_model


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(document_id: str = "test-doc") -> SessionState:
    """Return a minimal SessionState with confirmed W-2 fields."""
    return SessionState(
        document_id=document_id,
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        status="validated",
        confirmed_fields=ConfirmedFields(
            document_id=document_id,
            confirmed_fields={
                "form_type": FieldValue(value="W-2", source="user_confirmed", confidence=1.0),
                "box_1_wages": FieldValue(value="50000", source="user_confirmed", confidence=1.0),
                "box_2_federal_tax_withheld": FieldValue(value="6000", source="user_confirmed", confidence=1.0),
            },
        ),
        validation_output=ValidationOutput(status="ok"),
    )


def _make_report(document_id: str = "test-doc") -> TaxReport:
    return TaxReport(
        document_id=document_id,
        estimated_outcome="refund",
        estimated_amount=500.0,
        outcome_explanation="Test",
    )


# ---------------------------------------------------------------------------
# 1. llm_client — ensure_provider_configured
# ---------------------------------------------------------------------------

class TestEnsureProviderConfigured:
    def test_openai_configured_when_key_set(self):
        with patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            # Should not raise
            ensure_provider_configured("openai")

    def test_openai_raises_when_key_absent(self):
        with patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                ensure_provider_configured("openai")

    def test_anthropic_raises_when_key_absent(self):
        with patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = None
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                ensure_provider_configured("anthropic")

    def test_gemini_raises_when_key_absent(self):
        with patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                ensure_provider_configured("gemini")


# ---------------------------------------------------------------------------
# 2. llm_client — api_key inline precedence over env
# ---------------------------------------------------------------------------

class TestApiKeyPrecedence:
    """Inline api_key must override the env-configured key.

    We verify by checking which Authorization header reaches the HTTP call.
    """

    @pytest.mark.anyio
    async def test_inline_key_used_when_provided(self):
        """When api_key is supplied inline, it takes precedence over settings key."""
        from app.services.llm_client import chat

        captured_headers: dict = {}

        class FakeResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}]}

        async def fake_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return FakeResponse()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=fake_post)

        with patch("app.services.llm_client.settings") as mock_settings, \
             patch("app.services.llm_client.httpx.AsyncClient", return_value=mock_client):
            mock_settings.OPENAI_API_KEY = "env-key-should-not-be-used"
            mock_settings.OPENAI_MODEL = "gpt-4o"

            await chat(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                api_key="inline-key-wins",
            )

        assert captured_headers.get("Authorization") == "Bearer inline-key-wins"

    @pytest.mark.anyio
    async def test_env_key_used_when_no_inline_key(self):
        """When api_key is None, env key is used."""
        from app.services.llm_client import chat

        captured_headers: dict = {}

        class FakeResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"output": [{"type": "message", "content": [{"type": "output_text", "text": "hello"}]}]}

        async def fake_post(url, headers=None, json=None, **kwargs):
            captured_headers.update(headers or {})
            return FakeResponse()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=fake_post)

        with patch("app.services.llm_client.settings") as mock_settings, \
             patch("app.services.llm_client.httpx.AsyncClient", return_value=mock_client):
            mock_settings.OPENAI_API_KEY = "env-key-is-used"
            mock_settings.OPENAI_MODEL = "gpt-4o"

            await chat(
                model="gpt-4o",
                messages=[{"role": "user", "content": "hi"}],
                provider="openai",
                api_key=None,
            )

        assert captured_headers.get("Authorization") == "Bearer env-key-is-used"

    @pytest.mark.anyio
    async def test_no_key_anywhere_raises_before_http_call(self):
        """When api_key=None and no env key, ValueError before any HTTP call."""
        from app.services.llm_client import chat

        with patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.OPENAI_MODEL = "gpt-4o"

            with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                await chat(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": "hi"}],
                    provider="openai",
                    api_key=None,
                )


# ---------------------------------------------------------------------------
# 3. /api/analyze endpoint — model validation
# ---------------------------------------------------------------------------

class TestModelValidation:
    def setup_method(self):
        self.client = TestClient(app)

    def test_unknown_model_returns_422(self):
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "not-a-real-model", "api_key": "sk-test"},
            )
        assert resp.status_code == 422
        assert "not supported" in resp.json()["detail"]

    def test_valid_model_passes_validation(self):
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, return_value=_make_report()):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-test"},
            )
        assert resp.status_code == 200

    def test_ollama_accepts_any_model_name(self):
        """Ollama validation is skipped — any model name is accepted."""
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, return_value=_make_report()):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "ollama", "model": "my-custom-model:latest"},
            )
        assert resp.status_code == 200

    def test_no_model_uses_default(self):
        """Omitting model is valid — uses provider default."""
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, return_value=_make_report()):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "api_key": "sk-test"},
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 4. /api/analyze endpoint — api_key behavior
# ---------------------------------------------------------------------------

class TestApiKeyEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_inline_api_key_skips_env_check(self):
        """Provider with no env key configured should succeed when inline api_key given."""
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, return_value=_make_report()), \
             patch("app.core.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None  # not configured in env
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-inline-key"},
            )
        assert resp.status_code == 200

    def test_missing_env_key_and_no_inline_key_returns_400(self):
        """Cloud provider with no env key and no inline api_key returns 400."""
        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.services.llm_client.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "gpt-4o"},
            )
        assert resp.status_code == 400
        assert "OPENAI_API_KEY" in resp.json()["detail"]

    def test_401_from_provider_returns_authentication_failed(self):
        """When the cloud provider returns 401, the endpoint returns 400 with a safe message."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)

        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, side_effect=auth_error):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-wrong"},
            )
        assert resp.status_code == 400
        assert "Authentication failed" in resp.json()["detail"]
        # Confirm the actual key is not in the error message
        assert "sk-wrong" not in resp.json()["detail"]

    def test_403_from_provider_returns_authentication_failed(self):
        """403 is also treated as an authentication failure."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        auth_error = httpx.HTTPStatusError("403", request=MagicMock(), response=mock_response)

        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session"), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, side_effect=auth_error):
            resp = self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "anthropic", "model": "claude-sonnet-4-6", "api_key": "sk-ant-wrong"},
            )
        assert resp.status_code == 400
        assert "Authentication failed" in resp.json()["detail"]

    def test_api_key_not_stored_in_session(self):
        """The api_key must never be stored in the session state."""
        saved_sessions: list[SessionState] = []

        def capture_save(session: SessionState):
            saved_sessions.append(session)

        with patch("app.api.review.load_session", return_value=_make_session()), \
             patch("app.api.review.save_session", side_effect=capture_save), \
             patch("app.api.review.run_tax_analysis", new_callable=AsyncMock, return_value=_make_report()):
            self.client.post(
                "/api/analyze/test-doc",
                json={"provider": "openai", "model": "gpt-4o", "api_key": "sk-secret"},
            )

        assert saved_sessions, "save_session should have been called"
        for session in saved_sessions:
            if session.analysis_preferences:
                assert session.analysis_preferences.api_key is None, \
                    "api_key must not be persisted in session"


# ---------------------------------------------------------------------------
# 5. /health endpoint — provider configured status
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def setup_method(self):
        self.client = TestClient(app)

    def test_openai_configured_when_key_set(self):
        with patch("app.api.health.check_ollama_available", new_callable=AsyncMock, return_value=False), \
             patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test"
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["providers"]["openai"]["configured"] is True

    def test_openai_not_configured_when_key_absent(self):
        with patch("app.api.health.check_ollama_available", new_callable=AsyncMock, return_value=False), \
             patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["providers"]["openai"]["configured"] is False

    def test_all_cloud_providers_configured(self):
        with patch("app.api.health.check_ollama_available", new_callable=AsyncMock, return_value=True), \
             patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-openai"
            mock_settings.ANTHROPIC_API_KEY = "sk-anthropic"
            mock_settings.GEMINI_API_KEY = "AIza-gemini"
            resp = self.client.get("/health")
        data = resp.json()
        assert data["providers"]["openai"]["configured"] is True
        assert data["providers"]["anthropic"]["configured"] is True
        assert data["providers"]["gemini"]["configured"] is True

    def test_ollama_running_status_reflects_availability(self):
        with patch("app.api.health.check_ollama_available", new_callable=AsyncMock, return_value=True), \
             patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            resp = self.client.get("/health")
        assert resp.json()["providers"]["ollama"]["running"] is True
        assert resp.json()["providers"]["ollama"]["configured"] is True

    def test_ollama_not_running(self):
        with patch("app.api.health.check_ollama_available", new_callable=AsyncMock, return_value=False), \
             patch("app.api.health.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = None
            mock_settings.ANTHROPIC_API_KEY = None
            mock_settings.GEMINI_API_KEY = None
            resp = self.client.get("/health")
        assert resp.json()["providers"]["ollama"]["running"] is False


# ---------------------------------------------------------------------------
# 6. tax_advisor — auth errors propagate, generic errors fall back
# ---------------------------------------------------------------------------

class TestTaxAdvisorErrorHandling:
    @pytest.mark.anyio
    async def test_401_from_llm_propagates(self):
        """A 401 from the LLM should NOT be swallowed — it must propagate so review.py can
        return 'Authentication failed: check your API key.'"""
        from app.services.tax_advisor import _add_explanations
        from app.schemas.document import CalculationStep

        steps = [
            CalculationStep(
                step_number=1, label="Test", rule_reference="Test ref",
                input_value="$100", output_value="$50",
            )
        ]

        mock_response = MagicMock()
        mock_response.status_code = 401
        auth_error = httpx.HTTPStatusError("401 Unauthorized", request=MagicMock(), response=mock_response)

        with patch("app.services.tax_advisor.chat_json", new_callable=AsyncMock, side_effect=auth_error):
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                await _add_explanations(steps, AnalysisPreferences(
                    provider=LLMProvider.OPENAI, model="gpt-4o", api_key="bad-key"
                ))
            assert exc_info.value.response.status_code == 401

    @pytest.mark.anyio
    async def test_generic_exception_falls_back_to_templates(self):
        """Network errors (Ollama down, timeout) should silently fall back to templates."""
        from app.services.tax_advisor import _add_explanations
        from app.schemas.document import CalculationStep

        steps = [
            CalculationStep(
                step_number=1, label="Test", rule_reference="Test ref",
                input_value="$100", output_value="$50",
            )
        ]

        with patch("app.services.tax_advisor.chat_json", new_callable=AsyncMock,
                   side_effect=ConnectionError("Connection refused")):
            result = await _add_explanations(steps, None)

        assert len(result) == 1
        assert result[0].explanation  # template text, not empty
        assert "Test ref" in result[0].explanation  # uses rule_reference

    @pytest.mark.anyio
    async def test_5xx_from_provider_falls_back_to_templates(self):
        """Server errors (5xx) should fall back to templates, not surface as auth failures."""
        from app.services.tax_advisor import _add_explanations
        from app.schemas.document import CalculationStep

        steps = [
            CalculationStep(
                step_number=1, label="Test", rule_reference="Test ref",
                input_value="$100", output_value="$50",
            )
        ]

        mock_response = MagicMock()
        mock_response.status_code = 503
        server_error = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response)

        with patch("app.services.tax_advisor.chat_json", new_callable=AsyncMock, side_effect=server_error):
            result = await _add_explanations(steps, AnalysisPreferences(
                provider=LLMProvider.OPENAI, model="gpt-4o", api_key="sk-test"
            ))

        # Falls back to templates instead of raising
        assert len(result) == 1
        assert result[0].explanation
