"""Tests for the ``LLMClient`` abstraction layer.

Mocking strategy
----------------
``LLMClient`` accepts an optional ``client`` argument — tests pass a
``MagicMock`` that mimics ``google.genai.Client`` so no real API calls
are ever made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.llm_client import LLMClient, LLMClientError

# ── Helpers ───────────────────────────────────────────────────────────────


def _mock_sdk_client() -> MagicMock:
    """Return a ``MagicMock`` shaped like ``google.genai.Client``.

    The returned mock has ``.aio.models.generate_content`` set up as an
    ``AsyncMock`` so tests can configure return values / side effects.
    """
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock()
    return client


def _text_response(text: str) -> MagicMock:
    """Build a fake ``GenerateContentResponse`` with *text*."""
    resp = MagicMock()
    resp.text = text
    resp.parsed = None
    resp.prompt_feedback = None
    return resp


def _parsed_response(model_instance: object) -> MagicMock:
    """Build a fake ``GenerateContentResponse`` with a pre-parsed model."""
    resp = MagicMock()
    resp.text = None
    resp.parsed = model_instance
    resp.prompt_feedback = None
    return resp


# ── Construction ──────────────────────────────────────────────────────────


class TestLLMClientConstruction:
    """Tests centred on ``LLMClient.__init__``."""

    # A valid Pydantic model for structured-output tests below.
    # Defined here so it is available to the whole module.

    def test_raises_when_api_key_is_empty(self) -> None:
        """Passing an empty ``api_key`` (or no key in settings) raises
        ``LLMClientError``."""
        with pytest.raises(LLMClientError, match="No Google API key available"):
            LLMClient(api_key="")

    def test_accepts_explicit_api_key(self) -> None:
        """When an explicit non-empty ``api_key`` is provided, construction
        should succeed without consulting the settings singleton."""
        # Use a mock client so we never touch the real SDK.
        client = LLMClient(api_key="sk-test", client=MagicMock())
        assert client is not None

    def test_accepts_injected_client(self) -> None:
        """When ``client`` is injected directly, ``api_key`` can be anything
        (the injected client already carries credentials)."""
        fake = _mock_sdk_client()
        client = LLMClient(api_key="irrelevant", client=fake)
        assert client is not None


# ── generate() ────────────────────────────────────────────────────────────


class TestGenerate:
    """Tests for the ``generate`` method."""

    async def test_returns_text_when_sdk_succeeds(self) -> None:
        """A successful SDK call should return the response text verbatim."""
        fake = _mock_sdk_client()
        fake.aio.models.generate_content.return_value = _text_response("Hello world")
        client = LLMClient(api_key="sk-test", client=fake)

        result = await client.generate("Say hi")

        assert result == "Hello world"
        fake.aio.models.generate_content.assert_awaited_once()

    async def test_passes_system_instruction(self) -> None:
        """When ``system_instruction`` is provided it should be forwarded to
        the SDK config."""
        fake = _mock_sdk_client()
        fake.aio.models.generate_content.return_value = _text_response("Formal reply")
        client = LLMClient(api_key="sk-test", client=fake)

        await client.generate("Say hi", system_instruction="Be formal.")

        # The SDK client was called — verify config contained the instruction.
        _call_kwargs = fake.aio.models.generate_content.call_args.kwargs
        config = _call_kwargs.get("config")
        assert config is not None
        assert config.system_instruction == "Be formal."

    async def test_raises_on_empty_response(self) -> None:
        """If the SDK returns a response with ``text=None`` (e.g. blocked
        content) the client should raise ``LLMClientError``."""
        fake = _mock_sdk_client()
        blocked = _text_response("")
        blocked.text = None
        fake.aio.models.generate_content.return_value = blocked
        client = LLMClient(api_key="sk-test", client=fake)

        with pytest.raises(LLMClientError, match="empty response"):
            await client.generate("Say hi")

    async def test_wraps_sdk_api_error(self) -> None:
        """SDK ``APIError`` should be wrapped in ``LLMClientError``."""
        from google.genai.errors import APIError

        fake = _mock_sdk_client()
        fake.aio.models.generate_content.side_effect = APIError(
            code=429,
            response_json={"error": {"message": "Rate limited"}},
        )
        client = LLMClient(api_key="sk-test", client=fake)

        with pytest.raises(LLMClientError, match="Gemini API call failed"):
            await client.generate("Say hi")


# ── generate_structured() ────────────────────────────────────────────────


class TestGenerateStructured:
    """Tests for the ``generate_structured`` method."""

    # Define a simple Pydantic model for use in these tests.
    from pydantic import BaseModel

    class _DummySchema(BaseModel):
        name: str
        value: int

    async def test_returns_parsed_model(self) -> None:
        """When the SDK returns a populated ``.parsed`` the client should
        return it directly."""
        expected = self._DummySchema(name="test", value=42)
        fake = _mock_sdk_client()
        fake.aio.models.generate_content.return_value = _parsed_response(expected)
        client = LLMClient(api_key="sk-test", client=fake)

        result = await client.generate_structured(
            "Extract data",
            response_schema=self._DummySchema,
        )

        assert isinstance(result, self._DummySchema)
        assert result.name == "test"
        assert result.value == 42

    async def test_falls_back_to_json_parse(self) -> None:
        """When ``.parsed`` is ``None`` but ``.text`` contains valid JSON,
        the client should parse it via the Pydantic model."""
        fake = _mock_sdk_client()
        raw_resp = _text_response('{"name": "parsed", "value": 99}')
        raw_resp.parsed = None
        fake.aio.models.generate_content.return_value = raw_resp
        client = LLMClient(api_key="sk-test", client=fake)

        result = await client.generate_structured(
            "Extract data",
            response_schema=self._DummySchema,
        )

        assert isinstance(result, self._DummySchema)
        assert result.name == "parsed"
        assert result.value == 99

    async def test_raises_on_invalid_json(self) -> None:
        """When both ``.parsed`` and valid JSON text are absent, the client
        should raise ``LLMClientError``."""
        fake = _mock_sdk_client()
        raw_resp = _text_response("not valid json at all")
        raw_resp.parsed = None
        fake.aio.models.generate_content.return_value = raw_resp
        client = LLMClient(api_key="sk-test", client=fake)

        with pytest.raises(LLMClientError, match="could not be parsed"):
            await client.generate_structured(
                "Extract data",
                response_schema=self._DummySchema,
            )

    async def test_handles_dict_parsed(self) -> None:
        """If the SDK returns a plain ``dict`` as ``.parsed``, the client
        should coerce it via the Pydantic model."""
        fake = _mock_sdk_client()
        raw_resp = _text_response("")
        raw_resp.parsed = {"name": "from-dict", "value": 7}
        raw_resp.text = None
        fake.aio.models.generate_content.return_value = raw_resp
        client = LLMClient(api_key="sk-test", client=fake)

        result = await client.generate_structured(
            "Extract data",
            response_schema=self._DummySchema,
        )

        assert isinstance(result, self._DummySchema)
        assert result.name == "from-dict"
        assert result.value == 7

    async def test_raises_on_empty_response(self) -> None:
        """When the response has neither ``.parsed`` nor ``.text`` the
        client should raise ``LLMClientError``."""
        fake = _mock_sdk_client()
        raw_resp = _text_response("")
        raw_resp.parsed = None
        raw_resp.text = None
        fake.aio.models.generate_content.return_value = raw_resp
        client = LLMClient(api_key="sk-test", client=fake)

        with pytest.raises(LLMClientError, match="returned no data"):
            await client.generate_structured(
                "Extract data",
                response_schema=self._DummySchema,
            )

    async def test_sends_response_schema_to_sdk(self) -> None:
        """The ``response_schema`` and ``response_mime_type`` should be
        forwarded into the SDK ``GenerateContentConfig``."""
        fake = _mock_sdk_client()
        fake.aio.models.generate_content.return_value = _parsed_response(
            self._DummySchema(name="x", value=1)
        )
        client = LLMClient(api_key="sk-test", client=fake)

        await client.generate_structured(
            "Extract data",
            response_schema=self._DummySchema,
        )

        config = fake.aio.models.generate_content.call_args.kwargs.get("config")
        assert config is not None
        assert config.response_mime_type == "application/json"
        assert config.response_schema is self._DummySchema
