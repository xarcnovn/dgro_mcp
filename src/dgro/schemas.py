"""Structured outputs requested from the model. Each schema maps to one workflow step."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BriefDraft(BaseModel):
    title: str = Field(description="Specific case title, at most 60 characters.")
    category: str = Field(description="Kind of product or service, 1-4 words.")
    summary: str = Field(description="2-4 sentences a vendor can quote from.")
    requirements: list[str] = Field(description="Concrete, checkable requirements.")
    quantity: str = Field(description="Quantities or size of the job; empty if unknown.")
    location: str = Field(description="Where the work is done or goods are delivered; empty if unknown.")
    city: str = Field(description="City name only; empty if unknown.")
    country_code: str = Field(description="ISO 3166-1 alpha-2 country code, e.g. PL; empty if unknown.")
    budget: str = Field(description="Budget as stated by the requester; empty if unknown.")
    deadline: str = Field(description="Timing or deadline as stated by the requester; empty if unknown.")
    vendor_language: str = Field(description="ISO 639-1 code of the language local vendors use, e.g. pl.")
    search_queries: list[str] = Field(description="2-4 short web search queries in the vendor language.")
    questions: list[str] = Field(description="Up to 4 open questions that would materially change the quotes.")


class VendorCandidate(BaseModel):
    name: str
    website: str = Field(description="The business's own website URL, copied from the research; empty if none.")
    city: str
    description: str = Field(description="What they offer that is relevant to the case, one sentence.")
    relevance: str = Field(description="Why they fit this case, one short sentence.")
    email: str = Field(description="Public contact email if explicitly present in the research, else empty.")
    phone: str = Field(description="Public phone number if explicitly present in the research, else empty.")


class VendorList(BaseModel):
    vendors: list[VendorCandidate]


class EmailDraft(BaseModel):
    subject: str
    body: str = Field(description="Plain-text email body, no markdown or HTML.")


class EmailBody(BaseModel):
    body: str = Field(description="Plain-text email body, no markdown or HTML.")


class ReplyAnalysis(BaseModel):
    summary: str = Field(description="1-2 sentences: what the vendor said.")
    is_quote: bool = Field(description="True only if the email states a price or price range.")
    declined: bool = Field(description="True if the vendor says they cannot or will not do it.")
    total_price: float | None = Field(description="Total price for the full scope as a number; null if not stated.")
    currency: str = Field(description="ISO 4217 code such as PLN or EUR; empty if no price.")
    price_basis: Literal["fixed", "estimate", "range", "hourly", "per_unit", "unknown"]
    price_text: str = Field(description="The price statement in the vendor's own words, short.")
    timeline: str = Field(description="Start date, duration or delivery time offered; empty if not stated.")
    valid_until: str = Field(description="Offer validity; empty if not stated.")
    includes: list[str]
    excludes: list[str]
    conditions: str = Field(description="Payment terms, deposits, warranty and other conditions.")
    vendor_questions: list[str] = Field(description="Questions the vendor asks the requester.")
    missing_info: list[str] = Field(description="Information still needed to compare this offer.")
    fit_score: int = Field(description="0-100: how well the offer covers the requirements.")
    fit_notes: str = Field(description="One sentence explaining the fit score.")
    suggested_action: Literal["answer_questions", "request_missing_info", "negotiate", "consider", "none"]


class RankedOffer(BaseModel):
    vendor_id: int
    rank: int
    pros: list[str]
    cons: list[str]


class Comparison(BaseModel):
    headline: str = Field(description="One sentence recommendation.")
    recommended_vendor_id: int | None = Field(description="vendor_id of the best offer, null if none is acceptable yet.")
    rationale: str
    ranking: list[RankedOffer]
    risks: list[str]
    next_steps: list[str]
