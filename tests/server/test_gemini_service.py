"""Unit tests for server.services.gemini_service retry/fallback/timeout logic."""

import asyncio
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# We patch module-level globals before importing the module under test so that
# the test environment doesn't need a real API key or network access.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_gemini_module(monkeypatch):
    """Patch module-level state for every test."""
    import server.services.gemini_service as svc

    # Provide a mock client
    mock_client = MagicMock()
    monkeypatch.setattr(svc, "client", mock_client)

    # Use a deterministic fallback chain for tests
    monkeypatch.setattr(svc, "fallback_models", ["model-a", "model-b"])

    # Speed up retries (no real delay)
    monkeypatch.setattr(svc, "GEMINI_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(svc, "GEMINI_MAX_RETRIES", 2)
    monkeypatch.setattr(svc, "GEMINI_RETRY_BASE_DELAY", 0.0)

    return mock_client


# ===========================================================================
# _is_retryable_error
# ===========================================================================


class TestIsRetryableError:
    """Tests for _is_retryable_error helper."""

    def test_429_is_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("Status 429: rate limit")) is True

    def test_resource_exhausted_is_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("RESOURCE EXHAUSTED")) is True

    def test_503_is_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("503 Service Unavailable")) is True

    def test_service_unavailable_text_is_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("service unavailable")) is True

    def test_overloaded_is_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("Model overloaded")) is True

    def test_generic_error_not_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("Invalid argument")) is False

    def test_400_not_retryable(self):
        from server.services.gemini_service import _is_retryable_error

        assert _is_retryable_error(Exception("400 Bad Request")) is False


# ===========================================================================
# generate_with_retry_and_fallback
# ===========================================================================


class TestGenerateWithRetryAndFallback:
    """Tests for the retry + fallback orchestration."""

    @pytest.mark.asyncio
    async def test_first_model_succeeds(self, patch_gemini_module):
        """First model returns successfully — no fallback needed."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_client = patch_gemini_module
        mock_response = MagicMock()
        mock_response.text = "Success"
        mock_client.models.generate_content.return_value = mock_response

        result = await generate_with_retry_and_fallback([{"role": "user", "parts": [{"text": "hi"}]}])

        assert result == mock_response
        # Should only call once (first model, first attempt)
        assert mock_client.models.generate_content.call_count == 1
        call_kwargs = mock_client.models.generate_content.call_args[1]
        assert call_kwargs["model"] == "model-a"

    @pytest.mark.asyncio
    async def test_timeout_falls_through_to_next_model(self, patch_gemini_module):
        """Timeout on first model → immediately try next model (no retry)."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_client = patch_gemini_module
        mock_response = MagicMock()
        mock_response.text = "From model-b"

        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if kwargs["model"] == "model-a":
                raise asyncio.TimeoutError()
            return mock_response

        mock_client.models.generate_content.side_effect = side_effect

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                asyncio.TimeoutError(),  # model-a times out
                mock_response,           # model-b succeeds
            ]
            result = await generate_with_retry_and_fallback([])

        assert result == mock_response
        # model-a called once (no retry on timeout), model-b called once
        assert mock_gen.call_count == 2
        assert mock_gen.call_args_list[0][0][0] == "model-a"
        assert mock_gen.call_args_list[1][0][0] == "model-b"

    @pytest.mark.asyncio
    async def test_retryable_error_retries_then_succeeds(self, patch_gemini_module):
        """429 error → retries with backoff → succeeds on retry."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_response = MagicMock()
        mock_response.text = "Eventually worked"

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                Exception("429 Too Many Requests"),  # model-a attempt 1
                Exception("429 Too Many Requests"),  # model-a attempt 2 (retry 1)
                mock_response,                        # model-a attempt 3 (retry 2)
            ]
            result = await generate_with_retry_and_fallback([])

        assert result == mock_response
        # 3 attempts on model-a (initial + 2 retries), all for model-a
        assert mock_gen.call_count == 3
        for call in mock_gen.call_args_list:
            assert call[0][0] == "model-a"

    @pytest.mark.asyncio
    async def test_retryable_error_exhausts_retries_then_falls_back(self, patch_gemini_module):
        """429 error exhausts all retries → falls through to next model."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_response = MagicMock()
        mock_response.text = "model-b saved us"

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                Exception("429 Too Many Requests"),  # model-a attempt 1
                Exception("429 Too Many Requests"),  # model-a attempt 2
                Exception("429 Too Many Requests"),  # model-a attempt 3 (retries exhausted)
                mock_response,                        # model-b attempt 1
            ]
            result = await generate_with_retry_and_fallback([])

        assert result == mock_response
        # model-a: 3 attempts (exhausted), model-b: 1 attempt (success)
        assert mock_gen.call_count == 4
        assert mock_gen.call_args_list[3][0][0] == "model-b"

    @pytest.mark.asyncio
    async def test_all_models_timeout_raises_408(self, patch_gemini_module):
        """All models time out → HTTPException 408."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = asyncio.TimeoutError()

            with pytest.raises(HTTPException) as exc_info:
                await generate_with_retry_and_fallback([])

        assert exc_info.value.status_code == 408
        assert "timed out" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_all_models_retryable_error_raises_429(self, patch_gemini_module):
        """All models return retryable errors after exhausting retries → HTTPException 429."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            # model-a: 3 attempts (initial + 2 retries), model-b: 3 attempts
            mock_gen.side_effect = Exception("429 resource exhausted")

            with pytest.raises(HTTPException) as exc_info:
                await generate_with_retry_and_fallback([])

        assert exc_info.value.status_code == 429
        assert "rate limit" in exc_info.value.detail.lower() or "busy" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_all_models_non_retryable_error_raises_503(self, patch_gemini_module):
        """All models fail with non-retryable errors → HTTPException 503."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = Exception("Invalid API key")

            with pytest.raises(HTTPException) as exc_info:
                await generate_with_retry_and_fallback([])

        assert exc_info.value.status_code == 503
        assert "Invalid API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_retryable_error_skips_to_next_model_immediately(self, patch_gemini_module):
        """Non-retryable error on model-a → no retry, jump to model-b."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_response = MagicMock()

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                Exception("Permission denied"),  # model-a: non-retryable
                mock_response,                    # model-b: success
            ]
            result = await generate_with_retry_and_fallback([])

        assert result == mock_response
        # Only 1 attempt on model-a (no retry for non-retryable), then model-b
        assert mock_gen.call_count == 2
        assert mock_gen.call_args_list[0][0][0] == "model-a"
        assert mock_gen.call_args_list[1][0][0] == "model-b"

    @pytest.mark.asyncio
    async def test_mixed_errors_timeout_then_retryable_then_success(self, patch_gemini_module):
        """model-a times out, model-b gets 429 then succeeds on retry."""
        from server.services.gemini_service import generate_with_retry_and_fallback

        mock_response = MagicMock()

        with patch("server.services.gemini_service._generate_with_timeout", new_callable=AsyncMock) as mock_gen:
            mock_gen.side_effect = [
                asyncio.TimeoutError(),             # model-a: timeout → skip
                Exception("429 rate limited"),       # model-b: attempt 1
                mock_response,                       # model-b: attempt 2 (retry succeeds)
            ]
            result = await generate_with_retry_and_fallback([])

        assert result == mock_response
        assert mock_gen.call_count == 3


# ===========================================================================
# generate_stream
# ===========================================================================


class TestGenerateStream:
    """Tests for the streaming generator."""

    @pytest.mark.asyncio
    async def test_stream_first_model_succeeds(self, patch_gemini_module):
        """First model streams tokens successfully."""
        from server.services.gemini_service import generate_stream

        mock_client = patch_gemini_module
        chunk1 = MagicMock()
        chunk1.text = "Hello"
        chunk2 = MagicMock()
        chunk2.text = " world"
        chunk3 = MagicMock()
        chunk3.text = None  # Empty chunk should be skipped

        mock_client.models.generate_content_stream.return_value = [chunk1, chunk2, chunk3]

        tokens = []
        async for token in generate_stream([]):
            tokens.append(token)

        assert tokens == ["Hello", " world"]
        assert mock_client.models.generate_content_stream.call_count == 1
        call_kwargs = mock_client.models.generate_content_stream.call_args[1]
        assert call_kwargs["model"] == "model-a"

    @pytest.mark.asyncio
    async def test_stream_fallback_to_next_model(self, patch_gemini_module):
        """First model fails to stream → falls back to second model."""
        from server.services.gemini_service import generate_stream

        mock_client = patch_gemini_module
        chunk = MagicMock()
        chunk.text = "From backup"

        call_count = {"n": 0}

        def side_effect(**kwargs):
            call_count["n"] += 1
            if kwargs["model"] == "model-a":
                raise Exception("Connection reset")
            return [chunk]

        mock_client.models.generate_content_stream.side_effect = side_effect

        tokens = []
        async for token in generate_stream([]):
            tokens.append(token)

        assert tokens == ["From backup"]
        assert call_count["n"] == 2

    @pytest.mark.asyncio
    async def test_stream_all_models_fail_raises_503(self, patch_gemini_module):
        """All models fail to stream → HTTPException 503."""
        from server.services.gemini_service import generate_stream

        mock_client = patch_gemini_module
        mock_client.models.generate_content_stream.side_effect = Exception("Network error")

        with pytest.raises(HTTPException) as exc_info:
            async for _ in generate_stream([]):
                pass

        assert exc_info.value.status_code == 503
        assert "Network error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_stream_no_client_raises_500(self, monkeypatch):
        """client is None → HTTPException 500."""
        import server.services.gemini_service as svc

        monkeypatch.setattr(svc, "client", None)

        with pytest.raises(HTTPException) as exc_info:
            async for _ in svc.generate_stream([]):
                pass

        assert exc_info.value.status_code == 500
        assert "API key" in exc_info.value.detail
