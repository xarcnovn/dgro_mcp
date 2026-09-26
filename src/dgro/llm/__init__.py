from __future__ import annotations

from ..config import Settings
from .base import LLM, LLMError, LLMRefusal, ResearchResult, Source
from .fake_llm import FakeLLM

__all__ = ["LLM", "LLMError", "LLMRefusal", "ResearchResult", "Source", "FakeLLM", "build_llm"]


def build_llm(settings: Settings) -> LLM:
    if settings.effective_llm == "fake":
        return FakeLLM()
    from .anthropic_llm import AnthropicLLM

    return AnthropicLLM(settings)
