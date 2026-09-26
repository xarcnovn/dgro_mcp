"""Database models. A Case is the unit of work: everything else hangs off it."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow

# Case stages, in order. Derived from data (see Case.stage), never stored.
STAGES: list[tuple[str, str]] = [
    ("brief", "Brief"),
    ("vendors", "Vendors"),
    ("outreach", "Outreach"),
    ("quotes", "Quotes"),
    ("decision", "Decision"),
]


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    request_text: Mapped[str] = mapped_column(Text, default="")
    # open -> decided (offer chosen) -> closed; closed cases can be reopened.
    status: Mapped[str] = mapped_column(String(20), default="open")
    # draft (being structured / edited) -> confirmed (ready for vendor search)
    brief_status: Mapped[str] = mapped_column(String(20), default="draft")

    # Structured brief
    category: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    quantity: Mapped[str] = mapped_column(String(300), default="")
    location: Mapped[str] = mapped_column(String(300), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    country_code: Mapped[str] = mapped_column(String(2), default="")
    budget: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[str] = mapped_column(String(200), default="")
    vendor_language: Mapped[str] = mapped_column(String(10), default="en")
    search_queries: Mapped[list[str]] = mapped_column(JSON, default=list)
    # [{"question": str, "answer": str}]
    questions: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)

    # Requester identity used in outgoing emails
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_email: Mapped[str] = mapped_column(String(320), default="")
    contact_phone: Mapped[str] = mapped_column(String(60), default="")
    contact_company: Mapped[str] = mapped_column(String(200), default="")

    # Request-for-quote email template ({vendor_name} placeholder allowed)
    rfq_subject: Mapped[str] = mapped_column(String(300), default="")
    rfq_body: Mapped[str] = mapped_column(Text, default="")

    recommendation: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    chosen_vendor_id: Mapped[int | None] = mapped_column(Integer, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    vendors: Mapped[list[Vendor]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Vendor.id"
    )
    messages: Mapped[list[Message]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Message.id"
    )
    quotes: Mapped[list[Quote]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Quote.id"
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="case", cascade="all, delete-orphan", order_by="Event.id"
    )
    jobs: Mapped[list[Job]] = relationship(back_populates="case", cascade="all, delete-orphan", order_by="Job.id")

    # --- derived state ----------------------------------------------------------------------------
    @property
    def active_vendors(self) -> list[Vendor]:
        return [v for v in self.vendors if not v.excluded]

    @property
    def sent_messages(self) -> list[Message]:
        return [m for m in self.messages if m.direction == "out" and m.status == "sent"]

    @property
    def draft_messages(self) -> list[Message]:
        return [m for m in self.messages if m.direction == "out" and m.status == "draft"]

    @property
    def inbound_messages(self) -> list[Message]:
        return [m for m in self.messages if m.direction == "in"]

    @property
    def priced_quotes(self) -> list[Quote]:
        return [q for q in self.quotes if q.total_price is not None]

    @property
    def stage(self) -> str:
        if self.status in ("decided", "closed"):
            return "decision"
        if self.brief_status != "confirmed":
            return "brief"
        if self.quotes:
            return "decision" if len(self.quotes) >= 2 or self.chosen_vendor_id else "quotes"
        if self.sent_messages:
            return "quotes"
        if any(v.email for v in self.active_vendors):
            return "outreach"
        return "vendors"

    @property
    def stage_index(self) -> int:
        return [key for key, _ in STAGES].index(self.stage)

    @property
    def best_quote(self) -> Quote | None:
        priced = self.priced_quotes
        if not priced:
            return None
        currencies = {q.currency for q in priced}
        if len(currencies) > 1:
            return None  # not comparable without conversion
        return min(priced, key=lambda q: q.total_price or 0)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), default="")
    website: Mapped[str] = mapped_column(String(500), default="")
    domain: Mapped[str] = mapped_column(String(255), default="", index=True)
    city: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    relevance: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="search")  # search | manual

    email: Mapped[str] = mapped_column(String(320), default="")
    emails: Mapped[list[str]] = mapped_column(JSON, default=list)
    phones: Mapped[list[str]] = mapped_column(JSON, default=list)
    # pending | found | missing | manual | failed
    contact_status: Mapped[str] = mapped_column(String(20), default="pending")
    contact_note: Mapped[str] = mapped_column(Text, default="")

    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    excluded: Mapped[bool] = mapped_column(Boolean, default=False)
    declined: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    case: Mapped[Case] = relationship(back_populates="vendors")
    messages: Mapped[list[Message]] = relationship(back_populates="vendor", order_by="Message.id")
    quote: Mapped[Quote | None] = relationship(back_populates="vendor", uselist=False)

    @property
    def pipeline_status(self) -> str:
        if self.quote is not None and self.quote.status == "accepted":
            return "chosen"
        if self.declined:
            return "declined"
        if self.quote is not None:
            return "not chosen" if self.quote.status == "rejected" else "quoted"
        if any(m.direction == "in" for m in self.messages):
            return "replied"
        if any(m.direction == "out" and m.status in ("sent", "queued") for m in self.messages):
            return "contacted"
        if any(m.direction == "out" and m.status == "draft" for m in self.messages):
            return "draft"
        return "new"

    @property
    def has_rfq(self) -> bool:
        return any(m.direction == "out" and m.kind == "rfq" and m.status != "discarded" for m in self.messages)

    @property
    def thread(self) -> list[Message]:
        return [m for m in self.messages if m.status != "discarded"]

    @property
    def last_inbound(self) -> Message | None:
        inbound = [m for m in self.messages if m.direction == "in"]
        return inbound[-1] if inbound else None


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(3))  # out | in
    kind: Mapped[str] = mapped_column(String(20), default="rfq")  # rfq | reply
    # out: draft -> queued -> sent | failed ; discarded.  in: received
    status: Mapped[str] = mapped_column(String(20), default="draft")
    subject: Mapped[str] = mapped_column(String(500), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    body_full: Mapped[str] = mapped_column(Text, default="")  # inbound: original incl. quoted history
    from_addr: Mapped[str] = mapped_column(String(320), default="")
    to_addr: Mapped[str] = mapped_column(String(320), default="")
    rfc_message_id: Mapped[str] = mapped_column(String(500), default="", index=True)
    in_reply_to: Mapped[str] = mapped_column(String(500), default="")
    references: Mapped[str] = mapped_column(Text, default="")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    received_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    case: Mapped[Case] = relationship(back_populates="messages")
    vendor: Mapped[Vendor | None] = relationship(back_populates="messages")

    @property
    def timestamp(self) -> datetime:
        return self.received_at or self.sent_at or self.created_at


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id", ondelete="CASCADE"), unique=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id", ondelete="SET NULL"), default=None)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received | accepted | rejected
    source: Mapped[str] = mapped_column(String(20), default="email")  # email | manual
    revision: Mapped[int] = mapped_column(Integer, default=1)

    total_price: Mapped[float | None] = mapped_column(Float, default=None)
    currency: Mapped[str] = mapped_column(String(10), default="")
    price_basis: Mapped[str] = mapped_column(String(20), default="unknown")
    price_text: Mapped[str] = mapped_column(Text, default="")
    timeline: Mapped[str] = mapped_column(Text, default="")
    valid_until: Mapped[str] = mapped_column(String(200), default="")
    includes: Mapped[list[str]] = mapped_column(JSON, default=list)
    excludes: Mapped[list[str]] = mapped_column(JSON, default=list)
    conditions: Mapped[str] = mapped_column(Text, default="")
    missing_info: Mapped[list[str]] = mapped_column(JSON, default=list)
    vendor_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    fit_score: Mapped[int | None] = mapped_column(Integer, default=None)
    fit_notes: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    case: Mapped[Case] = relationship(back_populates="quotes")
    vendor: Mapped[Vendor] = relationship(back_populates="quote")


class Job(Base):
    """A unit of background work (AI step, scrape, send, inbox sync). Persisted so it survives restarts."""

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(200), default="")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # queued -> running -> succeeded | failed ; cancelled
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    case: Mapped[Case | None] = relationship(back_populates="jobs")


class Event(Base):
    """Human-readable activity log entry shown on the case timeline."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(10), default="info")  # info | success | warning | error
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    case: Mapped[Case] = relationship(back_populates="events")
