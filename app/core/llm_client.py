"""Injectable LLM client abstraction over Google Gemini.

Wraps the ``google-genai`` SDK so callers (intent analyser, reasoning
pipeline, …) never depend on the SDK directly — they depend on this
abstraction, which can be mocked or substituted in tests.
"""

from __future__ import annotations

from typing import Any, TypeVar

from google.genai import Client as GenAiClient
from google.genai import errors as sdk_errors
from google.genai.types import GenerateContentConfig
from langfuse import observe
from pydantic import BaseModel

from app.config.settings import get_settings

# ── Exception ────────────────────────────────────────────────────────────


class LLMClientError(Exception):
    """Raised when the underlying Gemini SDK call fails for any reason.

    This is the single error type consumers should catch so they don't
    need to import ``google.genai.errors`` themselves.
    """

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(message)


# ── Type variable for structured output ──────────────────────────────────

T = TypeVar("T", bound=BaseModel)

# ── Client ───────────────────────────────────────────────────────────────


class LLMClient:
    """Thin, injectable wrapper around ``google.genai.Client``.

    Usage (production)
    ------------------
    .. code-block:: python

        client = LLMClient()
        answer = await client.generate("What is the return policy?")
        structured = await client.generate_structured(
            "Extract: 30 days",
            response_schema=MyModel,
        )

    Usage (test / mock)
    -------------------
    Pass a pre-configured (or fake) ``client``::

        fake = MagicMock(spec=GenAiClient)
        client = LLMClient(client=fake)
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client: GenAiClient | None = None,
        vertexai_enabled: bool | None = None,
    ) -> None:
        """Initialise the client.

        Parameters
        ----------
        api_key:
            Gemini API key. Falls back to ``settings.google_api_key``.
            Not required when ``vertexai_enabled=True``.
        model_name:
            Gemini model name (e.g. ``"gemini-2.0-flash"``).
            Falls back to ``settings.gemini_model``.
        client:
            Pre-configured SDK client for dependency injection. When given,
            ``api_key`` and ``vertexai_enabled`` are ignored.
        vertexai_enabled:
            Use Vertex AI instead of a Google AI API key.
            Falls back to ``settings.vertexai_enabled``.
        """
        settings = get_settings()

        self._vertexai_enabled: bool = (
            vertexai_enabled
            if vertexai_enabled is not None
            else settings.vertexai_enabled
        )
        self._model_name: str = (
            model_name if model_name is not None else settings.gemini_model
        )

        if client is not None:
            self._client: GenAiClient = client
        elif self._vertexai_enabled:
            self._client = GenAiClient(
                vertexai=True,
                project=settings.gcp_project,
                location=settings.gcp_location,
            )
        else:
            resolved_key: str = api_key if api_key is not None else settings.google_api_key
            if not resolved_key:
                raise LLMClientError(
                    "No Google API key available. Set GOOGLE_API_KEY in your .env "
                    "or pass api_key to the constructor."
                )
            self._client = GenAiClient(api_key=resolved_key)

    @property
    def effective_audio_model(self) -> str:
        """Return the correct Gemini Live audio model based on the active provider."""
        settings = get_settings()
        if self._vertexai_enabled:
            return settings.gemini_audio_model_vertex
        return settings.gemini_audio_model

    # ── Public API ───────────────────────────────────────────────────────

    @observe()
    async def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
    ) -> str:
        """Send a text prompt to Gemini and return the response text.

        Parameters
        ----------
        prompt:
            The user message / question.
        system_instruction:
            Optional system-level instruction prepended to the conversation.

        Returns
        -------
        The model's response as plain text.

        Raises
        ------
        LLMClientError
            If the SDK call fails (network, auth, rate-limit, …).
        """
        config = GenerateContentConfig()
        if system_instruction is not None:
            config.system_instruction = system_instruction

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
        except (
            sdk_errors.APIError,
            sdk_errors.ClientError,
            sdk_errors.ServerError,
        ) as exc:
            raise LLMClientError(
                f"Gemini API call failed: {exc}",
                original=exc,
            ) from exc

        # The SDK's ``.text`` property concatenates all text parts from the
        # first candidate.  It returns ``None`` when the response is blocked.
        if response.text is None:
            feedback = _feedback_summary(response)
            raise LLMClientError(
                f"Gemini returned an empty response (blocked?). "
                f"Prompt feedback: {feedback}"
            )

        return response.text

    @observe()
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        system_instruction: str | None = None,
    ) -> T:
        """Request structured JSON output matching *response_schema*.

        This uses the SDK's native ``response_schema`` / ``response_mime_type``
        support so the model returns valid JSON that is automatically parsed
        into the requested Pydantic model.

        Parameters
        ----------
        prompt:
            The user message / question.
        response_schema:
            A Pydantic ``BaseModel`` subclass describing the expected shape.
        system_instruction:
            Optional system-level instruction.

        Returns
        -------
        An instance of *response_schema* populated from the model output.

        Raises
        ------
        LLMClientError
            If the SDK call fails or the response cannot be parsed.
        """
        config = GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        )
        if system_instruction is not None:
            config.system_instruction = system_instruction

        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
        except (
            sdk_errors.APIError,
            sdk_errors.ClientError,
            sdk_errors.ServerError,
        ) as exc:
            raise LLMClientError(
                f"Gemini structured API call failed: {exc}",
                original=exc,
            ) from exc

        # The SDK populates ``.parsed`` when ``response_schema`` is set.
        parsed = response.parsed
        if parsed is None:
            # Fallback: try to parse the raw text manually
            if response.text is not None:
                try:
                    return response_schema.model_validate_json(response.text)
                except Exception as exc:
                    raise LLMClientError(
                        f"Gemini returned text that could not be parsed as "
                        f"{response_schema.__name__}: {response.text!r}",
                        original=exc,
                    ) from exc
            feedback = _feedback_summary(response)
            raise LLMClientError(
                f"Gemini structured call returned no data. "
                f"Prompt feedback: {feedback}",
            )

        # ``parsed`` might already be the right type, but the SDK sometimes
        # returns a plain dict.  Normalise via the Pydantic model.
        if isinstance(parsed, response_schema):
            return parsed
        if isinstance(parsed, dict):
            return response_schema.model_validate(parsed)

        raise LLMClientError(
            f"Unexpected type from Gemini parsed output: "
            f"{type(parsed).__name__} (expected {response_schema.__name__})",
        )


# ── Internal helpers ─────────────────────────────────────────────────────


def _feedback_summary(response: Any) -> str:
    """Return a human-readable string from the response's prompt feedback."""
    try:
        fb = response.prompt_feedback
        if fb is None:
            return "no feedback"
        return f"block_reason={fb.block_reason}, safety_ratings={fb.safety_ratings}"
    except Exception:
        return "unavailable"
