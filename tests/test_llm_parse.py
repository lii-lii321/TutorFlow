import json

from app.services.parser import parse_message_smart
from tests.test_parser import FULL


class StubProvider:
    name = "openai"

    def __init__(self, reply: str):
        self.reply = reply
        self.calls = []

    async def complete(self, system, user):
        self.calls.append((system, user))
        return self.reply


async def test_llm_fills_fields_rules_missed():
    provider = StubProvider(json.dumps({"grade": "初三", "budget": 200}))
    ex = await parse_message_smart("你好", provider=provider)
    assert ex.parser == "llm"
    assert ex.fields["grade"] == "初三"
    assert ex.fields["budget"] == 200
    assert ex.missing == ["subject", "current_score", "target_score"]
    assert ex.confidence >= 0.85
    assert provider.calls[0][1] == "你好"


async def test_rules_win_on_conflict():
    provider = StubProvider(json.dumps({"grade": "初三", "budget": 999}))
    ex = await parse_message_smart(FULL, provider=provider)
    assert ex.parser == "llm"
    assert ex.fields["grade"] == "初二"
    assert ex.fields["budget"] == 150


async def test_non_json_reply_falls_back_to_rules():
    provider = StubProvider("抱歉，我无法解析该请求。")
    ex = await parse_message_smart("你好", provider=provider)
    assert ex.parser == "rules"
    assert ex.fields == {}
    assert ex.intent == "mid"


async def test_invalid_llm_intent_falls_back_to_base():
    provider = StubProvider(json.dumps({"grade": "初三", "intent": "very-high"}))
    ex = await parse_message_smart("你好", provider=provider)
    assert ex.parser == "llm"
    assert ex.intent == "mid"
