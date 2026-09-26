"""AnthropicLLM against a mocked Messages API: request shapes and response handling."""

from __future__ import annotations

import json

import anthropic
import httpx2
import pytest

from dgro.llm.anthropic_llm import FALLBACK_BETA, AnthropicLLM
from dgro.llm.base import LLMError, LLMRefusal
from dgro.schemas import BriefDraft, EmailDraft

from .conftest import make_settings

BRIEF = {
    "title": "Bathroom renovation, 9 m², Kraków",
    "category": "Bathroom renovation",
    "summary": "Full renovation of a 9 m² bathroom.",
    "requirements": ["Remove old tiles", "Walk-in shower"],
    "quantity": "9 m²",
    "location": "Kraków",
    "city": "Kraków",
    "country_code": "PL",
    "budget": "20 000 PLN",
    "deadline": "November",
    "vendor_language": "pl",
    "search_queries": ["remont łazienki Kraków"],
    "questions": [],
}


def message(content, stop_reason="end_turn", **usage):
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5",
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 50, **usage},
    }


class MockAPI:
    """Records requests and replies with queued responses."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        status, body = self.responses.pop(0)
        return httpx2.Response(status, json=body)

    def body(self, i=0) -> dict:
        return json.loads(self.requests[i].content)


def make_llm(tmp_path, api: MockAPI, **settings) -> AnthropicLLM:
    client = anthropic.Anthropic(
        api_key="test-key",
        base_url="http://api.test",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api)),
    )
    return AnthropicLLM(make_settings(tmp_path, llm="anthropic", **settings), client=client)


def test_structured_output_request_and_parse(tmp_path):
    api = MockAPI((200, message([
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": json.dumps(BRIEF)},
    ])))
    llm = make_llm(tmp_path, api)
    result = llm.structured(task="brief", prompt="Make a brief", schema=BriefDraft, effort="medium")

    assert result.title == BRIEF["title"]
    assert result.requirements == ["Remove old tiles", "Walk-in shower"]
    request = api.requests[0]
    assert request.url.path == "/v1/messages"
    betas = request.headers["anthropic-beta"]
    assert FALLBACK_BETA in betas
    body = api.body()
    assert body["model"] == "claude-opus-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "requirements" in body["output_config"]["format"]["schema"]["properties"]
    assert body["messages"] == [{"role": "user", "content": "Make a brief"}]
    assert "procurement assistant" in body["system"]


def test_refusal_raises(tmp_path):
    api = MockAPI((200, message([], stop_reason="refusal")))
    with pytest.raises(LLMRefusal):
        make_llm(tmp_path, api).structured(task="rfq", prompt="x", schema=EmailDraft)


def test_truncated_output_is_retryable(tmp_path):
    api = MockAPI((200, message([{"type": "text", "text": '{"subject": "Hi", "bo'}], stop_reason="max_tokens")))
    with pytest.raises(LLMError) as err:
        make_llm(tmp_path, api).structured(task="rfq", prompt="x", schema=EmailDraft)
    assert err.value.retryable
    assert "incomplete" in str(err.value)


def test_http_errors_are_translated(tmp_path):
    auth = MockAPI((401, {"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}))
    with pytest.raises(LLMError) as err:
        make_llm(tmp_path, auth).structured(task="rfq", prompt="x", schema=EmailDraft)
    assert "ANTHROPIC_API_KEY" in str(err.value) and not err.value.retryable

    limited = MockAPI((429, {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}}))
    with pytest.raises(LLMError) as err:
        make_llm(tmp_path, limited).structured(task="rfq", prompt="x", schema=EmailDraft)
    assert err.value.retryable


def test_legacy_model_skips_effort_and_fallbacks(tmp_path):
    api = MockAPI(
        (200, message([{"type": "text", "text": json.dumps({"subject": "S", "body": "B"})}])),
        (200, message([{"type": "text", "text": "Found: Firma | https://firma.pl"}])),
    )
    llm = make_llm(tmp_path, api, model="claude-haiku-4-5")
    llm.structured(task="rfq", prompt="x", schema=EmailDraft)
    body = api.body(0)
    assert "effort" not in body.get("output_config", {})
    assert "fallbacks" not in body
    llm.research(prompt="find", location=None, max_uses=3)
    assert api.body(1)["tools"][0]["type"] == "web_search_20250305"


SEARCH_TURN = [
    {"type": "text", "text": "Searching for bathroom renovation companies. "},
    {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search",
     "input": {"query": "remont łazienki Kraków"}},
    {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1", "content": [
        {"type": "web_search_result", "url": "https://lazienki-krakow.pl/", "title": "Łazienki Kraków",
         "encrypted_content": "enc-1", "page_age": "May 2026"},
        {"type": "web_search_result", "url": "https://remonty-nowak.pl/kontakt", "title": "Remonty Nowak",
         "encrypted_content": "enc-2", "page_age": None},
    ]},
]


def test_research_resumes_pause_turn_and_collects_sources(tmp_path):
    api = MockAPI(
        (200, message(SEARCH_TURN, stop_reason="pause_turn", server_tool_use={"web_search_requests": 1})),
        (200, message([
            {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_2", "content": [
                {"type": "web_search_result", "url": "https://hydro-bud.pl/", "title": "Hydro-Bud",
                 "encrypted_content": "enc-3", "page_age": None}]},
            {"type": "text", "text": "Łazienki Kraków | https://lazienki-krakow.pl/ | Kraków",
             "citations": [{"type": "web_search_result_location", "url": "https://lazienki-krakow.pl/",
                            "title": "Łazienki Kraków", "encrypted_index": "idx", "cited_text": "Remonty"}]},
        ], server_tool_use={"web_search_requests": 2})),
    )
    llm = make_llm(tmp_path, api)
    result = llm.research(prompt="Find vendors", location={"country": "PL", "city": "Kraków"}, max_uses=5)

    assert [s.url for s in result.sources] == [
        "https://lazienki-krakow.pl/", "https://remonty-nowak.pl/kontakt", "https://hydro-bud.pl/"]
    assert "lazienki-krakow.pl" in result.text
    assert result.searches == 3

    first, second = api.body(0), api.body(1)
    tool = first["tools"][0]
    assert tool == {"type": "web_search_20260209", "name": "web_search", "max_uses": 5,
                    "user_location": {"type": "approximate", "country": "PL", "city": "Kraków"}}
    # The paused turn goes back unchanged, with the same tools, and no extra user message.
    assert second["tools"] == first["tools"]
    assert second["messages"][0] == {"role": "user", "content": "Find vendors"}
    assert second["messages"][1]["role"] == "assistant"
    echoed = second["messages"][1]["content"]
    assert [b["type"] for b in echoed] == ["text", "server_tool_use", "web_search_tool_result"]
    assert echoed[2]["content"][0]["encrypted_content"] == "enc-1"
    assert len(second["messages"]) == 2


def test_research_retries_without_rejected_location(tmp_path):
    api = MockAPI(
        (400, {"type": "error", "error": {"type": "invalid_request_error",
                                          "message": "tools.0.user_location.country: unsupported country"}}),
        (200, message([{"type": "text", "text": "Firma | https://firma.pl"}])),
    )
    result = make_llm(tmp_path, api).research(prompt="find", location={"country": "XX"}, max_uses=2)
    assert "firma.pl" in result.text
    assert "user_location" not in api.body(1)["tools"][0]


def test_research_refusal(tmp_path):
    api = MockAPI((200, message([], stop_reason="refusal")))
    with pytest.raises(LLMRefusal):
        make_llm(tmp_path, api).research(prompt="find")
