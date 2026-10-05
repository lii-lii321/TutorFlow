import json

import httpx
import pytest

from app.config import settings
from app.services.llm.mock import MockProvider
from app.services.llm.openai_compat import OpenAICompatProvider
from app.services.llm.provider import get_provider
from app.services.parser import parse_message_smart


def test_get_provider_defaults_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "mock")
    monkeypatch.setattr(settings, "llm_api_key", "")
    assert isinstance(get_provider(), MockProvider)


def test_get_provider_selects_openai_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "sk-test")
    monkeypatch.setattr(settings, "llm_base_url", "https://llm.test/v1")
    monkeypatch.setattr(settings, "llm_model", "test-model")
    provider = get_provider()
    assert isinstance(provider, OpenAICompatProvider)
    assert provider.name == "openai"
    assert provider.model == "test-model"
    assert provider.base_url == "https://llm.test/v1"


def test_get_provider_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_api_key", "")
    assert isinstance(get_provider(), MockProvider)


def _provider_with(handler) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        base_url="https://llm.test/v1/",
        api_key="sk-test",
        model="test-model",
        transport=httpx.MockTransport(handler),
    )


async def test_openai_provider_round_trip():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"grade": "初三"}'}}]})

    provider = _provider_with(handler)
    reply = await provider.complete("提取字段", "孩子初三")

    assert reply == '{"grade": "初三"}'
    assert captured["url"] == "https://llm.test/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["temperature"] == 0.0
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "提取字段"},
        {"role": "user", "content": "孩子初三"},
    ]


async def test_openai_provider_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    provider = _provider_with(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete("s", "u")


async def test_provider_exception_falls_back_to_rules():
    class BoomProvider:
        name = "openai"

        async def complete(self, system, user):
            raise httpx.ConnectError("network down")

    ex = await parse_message_smart("你好", provider=BoomProvider())
    assert ex.parser == "rules"
    assert ex.intent == "mid"
