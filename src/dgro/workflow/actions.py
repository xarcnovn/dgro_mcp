"""Operations the user triggers from the UI. Each one changes the case and, where needed, queues a step.

Nothing here talks to Claude or the network directly; slow work always goes through the job queue.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db import utcnow
from ..models import Case, Event, Job, Message, Quote, Vendor
from ..services.mail import new_message_id, strip_quoted
from ..services.scraper import clean_email, normalize_url, site_domain
from .jobs import JobQueue, StepError
from .steps import render_template, reply_subject


class ActionError(Exception):
    """Invalid user action; the message is shown in the UI."""


def _event(db: Session, case: Case, message: str, level: str = "info") -> None:
    db.add(Event(case_id=case.id, level=level, message=message))


def _lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in (text or "").splitlines() if line.strip(" -•\t")]


def case_busy(db: Session, case_id: int) -> list[Job]:
    return list(db.scalars(select(Job).where(Job.case_id == case_id, Job.status.in_(("queued", "running")))
                           .order_by(Job.id)))


# --- case -----------------------------------------------------------------------------------------------
def create_case(db: Session, queue: JobQueue, settings: Settings, form: dict[str, str]) -> Case:
    request_text = (form.get("request_text") or "").strip()
    if len(request_text) < 10:
        raise ActionError("Describe what you need in at least a sentence.")
    case = Case(
        title=request_text.splitlines()[0][:80],
        request_text=request_text,
        location=(form.get("location") or "").strip()[:300],
        budget=(form.get("budget") or "").strip()[:200],
        deadline=(form.get("deadline") or "").strip()[:200],
        contact_name=(form.get("contact_name") or settings.requester_name).strip()[:200],
        contact_email=(form.get("contact_email") or settings.requester_email).strip()[:320],
        contact_phone=(form.get("contact_phone") or settings.requester_phone).strip()[:60],
        contact_company=(form.get("contact_company") or settings.requester_company).strip()[:200],
    )
    db.add(case)
    db.flush()
    _event(db, case, "Case created.")
    queue.enqueue(db, "structure_brief", case_id=case.id)
    return case


def save_brief(db: Session, queue: JobQueue, case: Case, form: dict[str, str], action: str) -> str:
    case.title = (form.get("title") or case.title).strip()[:200]
    case.summary = (form.get("summary") or "").strip()
    case.requirements = _lines(form.get("requirements", ""))
    for name, limit in (("category", 200), ("quantity", 300), ("location", 300), ("city", 120), ("budget", 200),
                        ("deadline", 200), ("contact_name", 200), ("contact_email", 320), ("contact_phone", 60),
                        ("contact_company", 200)):
        if name in form:
            setattr(case, name, (form.get(name) or "").strip()[:limit])
    country = (form.get("country_code") or "").strip().upper()
    case.country_code = country if re.fullmatch(r"[A-Z]{2}", country) else ""
    language = (form.get("vendor_language") or "en").strip().lower()
    case.vendor_language = language if re.fullmatch(r"[a-z]{2}", language) else "en"
    case.search_queries = _lines(form.get("search_queries", ""))
    questions = []
    for i, q in enumerate(case.questions or []):
        questions.append({"question": q["question"], "answer": (form.get(f"answer_{i}") or "").strip()})
    case.questions = questions

    if action == "refine":
        queue.enqueue(db, "structure_brief", case_id=case.id)
        _event(db, case, "Brief saved; asked Claude to refine it with your answers.")
        return "Refining the brief with your answers…"
    if action == "confirm":
        if not case.summary and not case.requirements:
            raise ActionError("The brief is empty - wait for the draft or fill in the summary first.")
        if not case.contact_name or not case.contact_email:
            raise ActionError("Add your name and email - vendors need to know who is asking.")
        case.brief_status = "confirmed"
        _event(db, case, "Brief confirmed.", "success")
        queue.enqueue(db, "find_vendors", case_id=case.id)
        if not case.rfq_body:
            queue.enqueue(db, "draft_rfq", case_id=case.id)
        return "Brief confirmed. Searching for vendors and drafting the quote request…"
    return "Brief saved."


def reopen_brief(db: Session, case: Case) -> None:
    case.brief_status = "draft"
    _event(db, case, "Brief reopened for editing.")


def set_case_status(db: Session, case: Case, status: str) -> None:
    if status not in ("open", "closed"):
        raise ActionError("Unknown status.")
    if status == "open" and case.status == "decided":
        case.chosen_vendor_id = None
        for quote in case.quotes:
            quote.status = "received"
    case.status = status
    _event(db, case, "Case closed." if status == "closed" else "Case reopened.")


# --- vendors -------------------------------------------------------------------------------------------
def search_vendors(db: Session, queue: JobQueue, case: Case) -> None:
    if case.brief_status != "confirmed":
        raise ActionError("Confirm the brief first.")
    queue.enqueue(db, "find_vendors", case_id=case.id)


def add_vendor(db: Session, queue: JobQueue, case: Case, form: dict[str, str]) -> Vendor:
    name = (form.get("name") or "").strip()
    website = normalize_url(form.get("website") or "")
    raw_email = (form.get("email") or "").strip()
    email = clean_email(raw_email)
    if raw_email and not email:
        raise ActionError(f"{raw_email!r} is not a valid email address.")
    if not name and not website:
        raise ActionError("Give the vendor a name or a website.")
    domain = site_domain(website) if website else ""
    if domain and any(v.domain == domain for v in case.vendors):
        raise ActionError(f"{domain} is already on the list.")
    vendor = Vendor(case=case, name=name or domain, website=website, domain=domain, source="manual",
                    email=email, emails=[email] if email else [],
                    contact_status="manual" if email else "pending",
                    description=(form.get("description") or "").strip())
    db.add(vendor)
    db.flush()
    if website and not email:
        queue.enqueue(db, "discover_contacts", case_id=case.id, payload={"vendor_id": vendor.id})
    elif not email:
        vendor.contact_status = "missing"
    _event(db, case, f"Vendor added manually: {vendor.name}.")
    return vendor


def update_vendor(db: Session, vendor: Vendor, form: dict[str, str]) -> None:
    if "email" in form:
        raw = (form.get("email") or "").strip()
        email = clean_email(raw)
        if raw and not email:
            raise ActionError(f"{raw!r} is not a valid email address.")
        if email != vendor.email:
            vendor.email = email
            vendor.contact_status = "manual" if email else "missing"
            if email and email not in (vendor.emails or []):
                vendor.emails = [*(vendor.emails or []), email]
    if "name" in form and form["name"].strip():
        vendor.name = form["name"].strip()[:300]


def set_vendor_flags(db: Session, vendor: Vendor, *, selected: bool | None = None,
                     excluded: bool | None = None) -> None:
    if selected is not None:
        vendor.selected = selected
    if excluded is not None:
        vendor.excluded = excluded
        if excluded:
            vendor.selected = False
            for msg in vendor.messages:
                if msg.status == "draft":
                    msg.status = "discarded"


def rescan_vendor(db: Session, queue: JobQueue, vendor: Vendor) -> None:
    if not vendor.website:
        raise ActionError("This vendor has no website to scan.")
    vendor.contact_status = "pending" if vendor.contact_status != "manual" else "manual"
    queue.enqueue(db, "discover_contacts", case_id=vendor.case_id, payload={"vendor_id": vendor.id})


# --- outreach ------------------------------------------------------------------------------------------
def save_rfq(db: Session, queue: JobQueue, case: Case, form: dict[str, str], action: str) -> str:
    if action == "generate":
        if case.brief_status != "confirmed":
            raise ActionError("Confirm the brief first.")
        queue.enqueue(db, "draft_rfq", case_id=case.id)
        return "Drafting the quote request email…"
    case.rfq_subject = (form.get("rfq_subject") or "").strip()[:300]
    case.rfq_body = (form.get("rfq_body") or "").strip()
    return "Email template saved."


def create_rfq_drafts(db: Session, case: Case, vendor_ids: list[int] | None = None) -> int:
    if not case.rfq_subject or not case.rfq_body:
        raise ActionError("Write or generate the quote request email first.")
    count = 0
    for vendor in case.active_vendors:
        if vendor_ids is not None and vendor.id not in vendor_ids:
            continue
        if vendor_ids is None and not vendor.selected:
            continue
        if not vendor.email or vendor.has_rfq:
            continue
        db.add(Message(case=case, vendor=vendor, direction="out", kind="rfq", status="draft",
                       subject=render_template(case.rfq_subject, vendor)[:500],
                       body=render_template(case.rfq_body, vendor), to_addr=vendor.email))
        count += 1
    if count:
        _event(db, case, f"{count} email draft(s) created - review and approve them.")
    return count


def update_draft(db: Session, msg: Message, form: dict[str, str]) -> None:
    if msg.status not in ("draft", "failed"):
        raise ActionError("Only drafts can be edited.")
    msg.subject = (form.get("subject") or msg.subject).strip()[:500]
    msg.body = (form.get("body") or msg.body).strip()
    to_addr = clean_email(form.get("to_addr") or "")
    if form.get("to_addr") and not to_addr:
        raise ActionError("Invalid recipient address.")
    if to_addr:
        msg.to_addr = to_addr


def approve_message(db: Session, queue: JobQueue, msg: Message) -> None:
    if msg.direction != "out" or msg.status not in ("draft", "failed"):
        raise ActionError("This message cannot be sent.")
    if not msg.body.strip() or not msg.subject.strip():
        raise ActionError("Subject and body cannot be empty.")
    if "[TODO" in msg.body:
        raise ActionError("The draft still contains [TODO: …] placeholders - fill them in first.")
    if not (msg.to_addr or (msg.vendor and msg.vendor.email)):
        raise ActionError("The vendor has no email address.")
    msg.status = "queued"
    msg.error = ""
    queue.enqueue(db, "send_message", case_id=msg.case_id, payload={"message_id": msg.id})


def approve_all(db: Session, queue: JobQueue, case: Case) -> tuple[int, list[str]]:
    sent, problems = 0, []
    for msg in case.draft_messages:
        try:
            approve_message(db, queue, msg)
            sent += 1
        except ActionError as exc:
            problems.append(f"{msg.vendor.name if msg.vendor else msg.to_addr}: {exc}")
    return sent, problems


def discard_message(db: Session, msg: Message) -> None:
    if msg.direction != "out" or msg.status not in ("draft", "failed"):
        raise ActionError("Only drafts can be discarded.")
    msg.status = "discarded"


def simulate_reply(db: Session, queue: JobQueue, vendor: Vendor, body: str) -> Message:
    """Sandbox mode: record a vendor reply typed or pasted by the user, exactly as if it came in by email."""
    body = (body or "").strip()
    if len(body) < 5:
        raise ActionError("Paste the vendor's reply text.")
    anchor = next((m for m in reversed(vendor.messages) if m.direction == "out" and m.status == "sent"), None)
    msg = Message(
        case_id=vendor.case_id,
        vendor=vendor,
        direction="in",
        kind="reply",
        status="received",
        simulated=True,
        subject=reply_subject(anchor.subject) if anchor else "Reply",
        body=strip_quoted(body),
        body_full=body,
        from_addr=vendor.email,
        rfc_message_id=new_message_id(vendor.email or "vendor@dgro.local"),
        in_reply_to=anchor.rfc_message_id if anchor else "",
        received_at=utcnow(),
    )
    db.add(msg)
    db.flush()
    _event(db, vendor.case, f"Reply from {vendor.name} recorded manually.")
    queue.enqueue(db, "analyze_reply", case_id=vendor.case_id, payload={"message_id": msg.id})
    return msg


def request_reply_draft(db: Session, queue: JobQueue, vendor: Vendor, intent: str, instructions: str) -> None:
    if intent not in ("clarify", "negotiate", "accept", "decline", "custom"):
        raise ActionError("Unknown reply type.")
    if intent == "custom" and not instructions.strip():
        raise ActionError("Tell Claude what the reply should say.")
    if not vendor.email and not vendor.last_inbound:
        raise ActionError("This vendor has no email address.")
    queue.enqueue(db, "draft_reply", case_id=vendor.case_id,
                  payload={"vendor_id": vendor.id, "intent": intent, "instructions": instructions.strip()[:2000]})


def sync_inbox(db: Session, queue: JobQueue, case_id: int | None = None) -> None:
    # The sync covers every open case; the case id only makes the progress visible on that case's page.
    queue.enqueue(db, "sync_inbox", case_id=case_id)


# --- quotes & decision ---------------------------------------------------------------------------------
def _parse_amount(raw: str) -> float | None:
    cleaned = re.sub(r"[\s ]", "", raw or "").replace(",", ".")
    if not cleaned:
        return None
    if cleaned.count(".") > 1:  # thousands separators such as 12.500.00
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    try:
        value = float(cleaned)
    except ValueError as exc:
        raise ActionError(f"{raw!r} is not a number.") from exc
    if value < 0:
        raise ActionError("Price cannot be negative.")
    return value


def save_manual_quote(db: Session, case: Case, form: dict[str, str]) -> Quote:
    try:
        vendor_id = int(form.get("vendor_id") or 0)
    except ValueError as exc:
        raise ActionError("Choose a vendor.") from exc
    vendor = db.get(Vendor, vendor_id)
    if vendor is None or vendor.case_id != case.id:
        raise ActionError("Choose a vendor.")
    quote = vendor.quote or Quote(case=case, vendor=vendor, revision=0)
    db.add(quote)
    quote.source = "manual"
    quote.revision = (quote.revision or 0) + 1
    quote.total_price = _parse_amount(form.get("total_price", ""))
    quote.currency = (form.get("currency") or quote.currency or "").strip().upper()[:10]
    quote.price_basis = form.get("price_basis") or quote.price_basis or "fixed"
    quote.price_text = (form.get("price_text") or "").strip() or quote.price_text
    quote.timeline = (form.get("timeline") or "").strip() or quote.timeline
    quote.summary = (form.get("notes") or "").strip() or quote.summary
    vendor.declined = False
    _event(db, case, f"Offer from {vendor.name} entered manually.")
    return quote


def choose_vendor(db: Session, case: Case, vendor: Vendor) -> None:
    if vendor.case_id != case.id or vendor.quote is None:
        raise ActionError("Only a vendor with an offer can be chosen.")
    case.chosen_vendor_id = vendor.id
    case.status = "decided"
    for quote in case.quotes:
        quote.status = "accepted" if quote.vendor_id == vendor.id else "rejected"
    _event(db, case, f"You chose {vendor.name}. Draft an acceptance and polite declines from the Quotes tab.",
           "success")


def draft_decision_emails(db: Session, queue: JobQueue, case: Case) -> int:
    if not case.chosen_vendor_id:
        raise ActionError("Choose an offer first.")
    count = 0
    for vendor in case.active_vendors:
        if vendor.declined or not vendor.email:
            continue
        if not any(m.direction == "out" and m.status == "sent" for m in vendor.messages):
            continue
        intent = "accept" if vendor.id == case.chosen_vendor_id else "decline"
        queue.enqueue(db, "draft_reply", case_id=case.id,
                      payload={"vendor_id": vendor.id, "intent": intent, "instructions": ""})
        count += 1
    return count


def compare(db: Session, queue: JobQueue, case: Case) -> None:
    if not case.quotes:
        raise ActionError("There are no offers to compare yet.")
    queue.enqueue(db, "compare_quotes", case_id=case.id)


def retry_job(db: Session, queue: JobQueue, job: Job) -> None:
    if job.status != "failed":
        raise ActionError("Only failed jobs can be retried.")
    if job.kind == "send_message":
        msg = db.get(Message, job.payload.get("message_id"))
        if msg is not None and msg.status == "failed":
            msg.status = "queued"
    job.status = "cancelled"
    queue.enqueue(db, job.kind, case_id=job.case_id, payload=dict(job.payload))


def delete_case(db: Session, case: Case) -> None:
    db.delete(case)


def summarize_problem(exc: Exception) -> str:
    if isinstance(exc, (ActionError, StepError)):
        return str(exc)
    return f"Unexpected error: {exc}"


def form_to_dict(form: Any) -> dict[str, str]:
    return {k: (v if isinstance(v, str) else "") for k, v in form.items()}
