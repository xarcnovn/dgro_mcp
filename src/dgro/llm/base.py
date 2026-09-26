"""Interface every model backend implements. The workflow only talks to this."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """A model call failed. `retryable` tells the job runner whether trying again later can help."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class LLMRefusal(LLMError):
    """The model (and any fallback model) declined the request."""


@dataclass
class Source:
    url: str
    title: str = ""


@dataclass
class ResearchResult:
    text: str
    sources: list[Source] = field(default_factory=list)
    searches: int = 0


class LLM(Protocol):
    name: str

    def structured(
        self,
        *,
        task: str,
        prompt: str,
        schema: type[T],
        effort: str = "medium",
        context: dict[str, Any] | None = None,
    ) -> T:
        """Return an instance of `schema`. `context` is the data the prompt was rendered from."""
        ...

    def research(
        self,
        *,
        prompt: str,
        location: dict[str, str] | None = None,
        max_uses: int = 6,
        context: dict[str, Any] | None = None,
    ) -> ResearchResult:
        """Search the web and return findings as text plus the sources that were seen."""
        ...
