"""LLMClient falls back to the next model on overload errors only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.genai import errors as sdk_errors

from app.core.llm_client import LLMClient, LLMClientError


def _client(side_effect):
    fake = MagicMock()
    fake.aio.models.generate_content = AsyncMock(side_effect=side_effect)
    llm = LLMClient(client=fake, model_name="primary")
    llm._models = ["primary", "backup"]
    return llm, fake.aio.models.generate_content


def _err(cls, code):
    return cls(code, {"error": {"code": code, "message": "x", "status": "X"}})


async def test_503_falls_back_to_next_model():
    llm, call = _client([_err(sdk_errors.ServerError, 503), SimpleNamespace(text="ok")])
    assert await llm.generate("hi") == "ok"
    assert [c.kwargs["model"] for c in call.call_args_list] == ["primary", "backup"]


async def test_400_does_not_fall_back():
    llm, call = _client([_err(sdk_errors.ClientError, 400)])
    with pytest.raises(LLMClientError):
        await llm.generate("hi")
    assert call.call_count == 1


async def test_all_models_overloaded_raises():
    llm, call = _client([_err(sdk_errors.ClientError, 429), _err(sdk_errors.ServerError, 503)])
    with pytest.raises(LLMClientError, match="503"):
        await llm.generate("hi")
    assert call.call_count == 2


async def test_retired_model_404_falls_back():
    llm, call = _client([_err(sdk_errors.ClientError, 404), SimpleNamespace(text="ok")])
    assert await llm.generate("hi") == "ok"
