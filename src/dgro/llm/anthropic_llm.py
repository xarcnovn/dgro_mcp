"""Claude backend built on the official Anthropic Python SDK.

- Structured steps use `messages.parse` with a Pydantic schema (structured outputs), so results always validate.
- Vendor research uses the server-side web search tool; `pause_turn` responses are resumed.
- Declined requests can be retried server-side on another model (`fallbacks="default"`).
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
import pydantic

from ..config import Settings
from .base import LLMError, LLMRefusal, ResearchResult, Source, T
from .prompts import SYSTEM

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_CONTINUATIONS = 5
MAX_TOKENS = 16000

# Models documented to support `fallbacks="default"`.
_FALLBACK_MODELS = ("claude-opus-5", "claude-fable-5")
# Older models: no `effort` parameter and only the basic web search tool.
_LEGACY_PREFIXES = ("claude-haiku-4-5", "claude-sonnet-4-5", "claude-opus-4-5", "claude-opus-4-1", "claude-opus-4-0",
                    "claude-sonnet-4-0", "claude-3")


def _is_legacy(model: str) -> bool:
    return model.startswith(_LEGACY_PREFIXES) or "haiku" in model


def web_search_tool(model: str, max_uses: int, location: dict[str, str] | None) -> dict[str, Any]:
    # web_search_20260209 adds dynamic filtering (Claude filters results with code before they reach context).
    tool: dict[str, Any] = {
        "type": "web_search_20250305" if _is_legacy(model) else "web_search_20260209",
        "name": "web_search",
        "max_uses": max_uses,
    }
    if location:
        tool["user_location"] = {"type": "approximate", **location}
    return tool


class AnthropicLLM:
    name = "anthropic"

    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None):
        self.model = settings.model
        self.client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key or None,  # None: SDK resolves env vars / `ant auth login` profile
            max_retries=3,
            timeout=anthropic.Timeout(settings.llm_timeout_seconds, connect=10.0),
        )
        self.use_fallbacks = settings.refusal_fallback and self.model.startswith(_FALLBACK_MODELS)

    # ------------------------------------------------------------------------------------------------
    def _common(self, effort: str) -> dict[str, Any]:
        params: dict[str, Any] = {"model": self.model, "max_tokens": MAX_TOKENS, "system": SYSTEM}
        if not _is_legacy(self.model):
            params["output_config"] = {"effort": effort}
        if self.use_fallbacks:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def structured(
        self,
        *,
        task: str,
        prompt: str,
        schema: type[T],
        effort: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> T:
        try:
            response = self.client.beta.messages.parse(
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                **self._common(effort),
            )
        except pydantic.ValidationError as exc:
            # Usually output cut off at max_tokens; thinking length varies, so a retry normally succeeds.
            raise LLMError(f"{task}: model output was incomplete or did not match the schema "
                           f"({exc.error_count()} errors)", retryable=True) from exc
        except anthropic.APIError as exc:
            raise _translate(exc, task) from exc

        _check_stop(response, task)
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError(f"{task}: model returned no structured output (stop_reason={response.stop_reason})",
                           retryable=True)
        log.info("%s: %s in / %s out tokens", task, response.usage.input_tokens, response.usage.output_tokens)
        return parsed

    def research(
        self,
        *,
        prompt: str,
        location: dict[str, str] | None = None,
        max_uses: int = 6,
        context: dict[str, Any] | None = None,
    ) -> ResearchResult:
        try:
            return self._research(prompt, location, max_uses)
        except anthropic.BadRequestError as exc:
            if not (location and "location" in str(exc).lower()):
                raise _translate(exc, "research") from exc
            # e.g. an unsupported country code: search without localisation instead of failing
            log.warning("web search rejected user_location %s; retrying without it", location)
        except anthropic.APIError as exc:
            raise _translate(exc, "research") from exc
        try:
            return self._research(prompt, None, max_uses)
        except anthropic.APIError as exc:
            raise _translate(exc, "research") from exc

    def _research(self, prompt: str, location: dict[str, str] | None, max_uses: int) -> ResearchResult:
        messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
        tools = [web_search_tool(self.model, max_uses, location)]
        texts: list[str] = []
        sources: dict[str, Source] = {}
        searches = 0

        for _ in range(MAX_CONTINUATIONS + 1):
            response = self.client.beta.messages.create(messages=messages, tools=tools, **self._common("medium"))
            if response.stop_reason == "refusal":
                raise LLMRefusal("research: the model declined this request")
            for block in response.content:
                if block.type == "text":
                    texts.append(block.text)
                elif block.type == "web_search_tool_result" and isinstance(block.content, list):
                    for result in block.content:
                        url = getattr(result, "url", "")
                        if url and url not in sources:
                            sources[url] = Source(url=url, title=getattr(result, "title", "") or "")
            server_usage = getattr(response.usage, "server_tool_use", None)
            searches += getattr(server_usage, "web_search_requests", 0) or 0
            if response.stop_reason != "pause_turn":
                break
            # The server paused a long search turn: send the paused content back unchanged (with the same
            # tools) so it resumes. Consecutive assistant messages are merged into one turn by the API.
            messages.append({"role": "assistant", "content": response.content})

        text = "".join(texts).strip()
        if not text and not sources:
            raise LLMError("research: web search returned nothing", retryable=True)
        return ResearchResult(text=text, sources=list(sources.values()), searches=searches)


def _check_stop(response: Any, task: str) -> None:
    if response.stop_reason == "refusal":
        raise LLMRefusal(f"{task}: the model declined this request")
    if response.stop_reason == "max_tokens":
        raise LLMError(f"{task}: output was truncated (max_tokens)", retryable=False)


def _translate(exc: anthropic.APIError, task: str) -> LLMError:
    if isinstance(exc, anthropic.AuthenticationError):
        return LLMError("Claude API authentication failed - check ANTHROPIC_API_KEY.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return LLMError(f"{task}: the API key is not allowed to do this ({exc.message}).")
    if isinstance(exc, anthropic.NotFoundError):
        return LLMError(f"{task}: model or endpoint not found - check DGRO_MODEL ({exc.message}).")
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError(f"{task}: rate limited by the Claude API.", retryable=True)
    if isinstance(exc, anthropic.BadRequestError):
        return LLMError(f"{task}: request rejected by the Claude API: {exc.message}")
    if isinstance(exc, anthropic.APIStatusError):
        return LLMError(f"{task}: Claude API error {exc.status_code}: {exc.message}", retryable=exc.status_code >= 500)
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError(f"{task}: could not reach the Claude API ({exc.__class__.__name__}).", retryable=True)
    return LLMError(f"{task}: {exc}", retryable=True)
