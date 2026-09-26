"""The case workflow. Each function is one background step, run by the job worker.

    brief -> vendors (web search) -> contacts (scrape) -> RFQ email -> [human approves] -> send
          -> inbox sync -> reply analysis (quote extraction) -> [reply drafts, human approves] -> comparison

The order is fixed in code; Claude is called only inside a step, for a narrow task with a typed result.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from ..db import utcnow
from ..llm import prompts
from ..models import Case, Message, Quote, Vendor
from ..schemas import BriefDraft, Comparison, EmailBody, EmailDraft, ReplyAnalysis, VendorList
from ..services.mail import HeaderInfo, OutgoingEmail, new_message_id
from ..services.scraper import (
    ContactScraper,
    clean_email,
    is_directory,
    is_reserved_domain,
    normalize_url,
    pick_best_email,
    site_domain,
)
from .jobs import StepContext, StepError


# --- helpers -----------------------------------------------------------------------------------------
def case_dict(case: Case) -> dict[str, Any]:
    return {
        "title": case.title,
        "request_text": case.request_text,
        "category": case.category,
        "summary": case.summary,
        "requirements": list(case.requirements or []),
        "quantity": case.quantity,
        "location": case.location,
        "city": case.city,
        "country_code": case.country_code,
        "budget": case.budget,
        "deadline": case.deadline,
        "vendor_language": case.vendor_language,
        "search_queries": list(case.search_queries or []),
        "questions": [dict(q) for q in case.questions or []],
        "contact_name": case.contact_name,
        "contact_email": case.contact_email,
        "contact_phone": case.contact_phone,
        "contact_company": case.contact_company,
    }


def quote_dict(quote: Quote) -> dict[str, Any]:
    return {
        "vendor_id": quote.vendor_id,
        "vendor_name": quote.vendor.name,
        "total_price": quote.total_price,
        "currency": quote.currency,
        "price_basis": quote.price_basis,
        "price_text": quote.price_text,
        "timeline": quote.timeline,
        "valid_until": quote.valid_until,
        "includes": list(quote.includes or []),
        "excludes": list(quote.excludes or []),
        "conditions": quote.conditions,
        "missing_info": list(quote.missing_info or []),
        "vendor_questions": list(quote.vendor_questions or []),
        "fit_score": quote.fit_score,
        "summary": quote.summary,
    }


def _get_case(ctx: StepContext, case_id: int) -> Case:
    case = ctx.db.get(Case, case_id)
    if case is None:
        raise StepError(f"case {case_id} no longer exists")
    return case


def render_template(text: str, vendor: Vendor) -> str:
    return text.replace("{vendor_name}", (vendor.name or vendor.domain).strip())


def _to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def reply_subject(subject: str) -> str:
    base = re.sub(r"^\s*((re|odp|aw|sv|fw|fwd)\s*:\s*)+", "", subject or "", flags=re.IGNORECASE)
    return f"Re: {base}".strip()


# --- steps ---------------------------------------------------------------------------------------------
def structure_brief(ctx: StepContext, case_id: int) -> None:
    case = _get_case(ctx, case_id)
    data = case_dict(case)
    draft = ctx.llm.structured(task="brief", prompt=prompts.brief_prompt(data), schema=BriefDraft,
                               effort="medium", context={"case": data})
    case.title = draft.title.strip()[:200] or case.title
    case.category = draft.category.strip()[:200]
    case.summary = draft.summary.strip()
    case.requirements = [r.strip() for r in draft.requirements if r.strip()]
    case.quantity = case.quantity or draft.quantity.strip()[:300]
    case.location = case.location or draft.location.strip()[:300]
    case.city = draft.city.strip()[:120] or case.city
    country = draft.country_code.strip().upper()
    case.country_code = country if re.fullmatch(r"[A-Z]{2}", country) else case.country_code
    case.budget = case.budget or draft.budget.strip()[:200]
    case.deadline = case.deadline or draft.deadline.strip()[:200]
    language = draft.vendor_language.strip().lower()
    case.vendor_language = language if re.fullmatch(r"[a-z]{2}", language) else "en"
    case.search_queries = [q.strip() for q in draft.search_queries if q.strip()][:5]
    answered = [q for q in case.questions or [] if q.get("answer", "").strip()]
    known = {q["question"].strip().lower() for q in answered}
    new = [{"question": q.strip(), "answer": ""} for q in draft.questions[:4]
           if q.strip() and q.strip().lower() not in known]
    case.questions = answered + new
    ctx.event(case.id, f"Brief drafted: {len(case.requirements)} requirements"
                       + (f", {len(new)} open questions for you." if new else ", no open questions."), "success")


def find_vendors(ctx: StepContext, case_id: int) -> None:
    case = _get_case(ctx, case_id)
    settings = ctx.settings
    data = case_dict(case)
    known_domains = sorted({v.domain for v in case.vendors if v.domain})
    context = {"case": data, "max_vendors": settings.max_vendors, "exclude_domains": known_domains}
    location: dict[str, str] | None = None
    if case.country_code:
        location = {"country": case.country_code}
        if case.city:
            location["city"] = case.city

    research = ctx.llm.research(
        prompt=prompts.research_prompt(data, settings.max_vendors, known_domains),
        location=location,
        max_uses=settings.web_search_max_uses,
        context=context,
    )
    sources = [{"url": s.url, "title": s.title} for s in research.sources[:60]]
    found = ctx.llm.structured(
        task="vendors",
        prompt=prompts.vendor_extract_prompt(research.text, sources, settings.max_vendors),
        schema=VendorList,
        effort="low",
        context=context,
    )

    added: list[Vendor] = []
    seen = set(known_domains)
    seen_emails = {v.email for v in case.vendors if v.email}
    for cand in found.vendors[: settings.max_vendors]:
        website = normalize_url(cand.website)
        domain = site_domain(website) if website else ""
        email = clean_email(cand.email)
        if domain and (domain in seen or is_directory(domain)):
            continue
        if (not domain and not email) or (email and email in seen_emails):
            continue
        seen.add(domain)
        seen_emails.add(email)
        vendor = Vendor(
            case=case,
            name=(cand.name.strip() or domain)[:300],
            website=website,
            domain=domain,
            city=cand.city.strip()[:120],
            description=cand.description.strip(),
            relevance=cand.relevance.strip(),
            source="search",
            email=email,
            emails=[email] if email else [],
            phones=[cand.phone.strip()] if cand.phone.strip() else [],
            contact_status="pending",
        )
        ctx.db.add(vendor)
        ctx.db.flush()
        added.append(vendor)
        ctx.enqueue("discover_contacts", case_id=case.id, payload={"vendor_id": vendor.id})

    searched = f"{research.searches} web searches, " if research.searches else ""
    if added:
        ctx.event(case.id, f"Vendor search: {searched}{len(added)} new vendors found. Looking up their contact "
                           "details now.", "success")
    else:
        ctx.event(case.id, f"Vendor search: {searched}no new vendors found. Adjust the search queries in the "
                           "brief or add vendors manually.", "warning")


def discover_contacts(ctx: StepContext, vendor_id: int) -> None:
    vendor = ctx.db.get(Vendor, vendor_id)
    if vendor is None:
        return
    settings = ctx.settings
    note = ""
    if vendor.website:
        with ContactScraper(max_pages=settings.scrape_max_pages, timeout=settings.scrape_timeout_seconds,
                            allow_private=settings.scrape_allow_private_hosts) as scraper:
            result = scraper.scrape(vendor.website)
        vendor.emails = list(dict.fromkeys([*(vendor.emails or []), *result.emails]))
        vendor.phones = list(dict.fromkeys([*(vendor.phones or []), *result.phones]))[:5]
        note = result.error or f"Scanned {len(result.pages)} page(s)."
    if vendor.contact_status != "manual" or not vendor.email:
        vendor.email = pick_best_email(vendor.emails, vendor.domain)
    vendor.contact_note = note
    if vendor.email:
        vendor.contact_status = "manual" if vendor.contact_status == "manual" else "found"
    else:
        vendor.contact_status = "missing"
        ctx.event(vendor.case_id, f"No email found for {vendor.name}. Add one on the Vendors tab if you want to "
                                  "contact them.", "warning")


def draft_rfq(ctx: StepContext, case_id: int) -> None:
    case = _get_case(ctx, case_id)
    data = case_dict(case)
    draft = ctx.llm.structured(task="rfq", prompt=prompts.rfq_prompt(data), schema=EmailDraft, effort="medium",
                               context={"case": data})
    case.rfq_subject = draft.subject.strip()[:300]
    case.rfq_body = draft.body.strip()
    ctx.event(case.id, "Quote request email drafted. Review it on the Outreach tab before anything is sent.",
              "success")


def send_message(ctx: StepContext, message_id: int) -> None:
    msg = ctx.db.get(Message, message_id)
    if msg is None or msg.status not in ("queued", "failed"):
        return  # already sent, discarded, or delivery state unknown
    case, vendor = msg.case, msg.vendor
    settings = ctx.settings
    sender = settings.sender_address or case.contact_email
    to_addr = msg.to_addr or (vendor.email if vendor else "")
    if not sender:
        msg.status = "failed"
        msg.error = "No sender address: set DGRO_EMAIL_FROM (or your email in the case contact details)."
        ctx.event(case.id, msg.error, "error")
        return
    if not to_addr:
        msg.status = "failed"
        msg.error = "The vendor has no email address."
        return
    if ctx.mail.name != "sandbox" and is_reserved_domain(to_addr) and not settings.email_redirect_to:
        msg.status = "failed"
        msg.error = f"{to_addr} is a reserved demo address and cannot receive email."
        ctx.event(case.id, msg.error, "error")
        return

    msg.rfc_message_id = msg.rfc_message_id or new_message_id(sender)
    msg.from_addr = sender
    msg.to_addr = to_addr
    msg.status = "sending"
    ctx.db.commit()  # persist before talking to SMTP so a crash never causes a duplicate send

    outgoing = OutgoingEmail(
        to_addr=to_addr,
        subject=msg.subject,
        body=msg.body,
        from_addr=sender,
        from_name=case.contact_name,  # no Reply-To: replies must come back to the mailbox dgro reads
        message_id=msg.rfc_message_id,
        in_reply_to=msg.in_reply_to,
        references=msg.references.split(),
    )
    try:
        note = ctx.mail.send(outgoing)
    except Exception as exc:
        msg.status = "failed"
        msg.error = str(exc) or exc.__class__.__name__
        ctx.db.commit()
        raise StepError(f"Sending to {to_addr} failed: {msg.error}",
                        retryable=isinstance(exc, (OSError, TimeoutError))) from exc
    msg.status = "sent"
    msg.error = ""
    msg.sent_at = utcnow()
    ctx.event(case.id, f"Email to {vendor.name if vendor else to_addr}: {note}.", "success")
    ctx.db.commit()
    if settings.send_delay_seconds > 0:
        time.sleep(settings.send_delay_seconds)  # pace outgoing mail


def sync_inbox(ctx: StepContext) -> None:
    mail = ctx.mail
    if not mail.can_receive:
        return
    sent = [m for m in ctx.db.query(Message).filter(Message.direction == "out", Message.status == "sent")
            if m.case.status != "closed" and m.rfc_message_id]
    if not sent:
        return
    by_id = {m.rfc_message_id: m for m in sent}
    by_sender: dict[str, Vendor] = {}
    for m in sorted(sent, key=lambda m: m.sent_at or m.created_at):
        if m.vendor and m.vendor.email:
            by_sender[m.vendor.email.lower()] = m.vendor  # latest outreach wins
    known = {m.rfc_message_id for m in ctx.db.query(Message).filter(Message.direction == "in")}
    since = min(m.sent_at or m.created_at for m in sent) - timedelta(days=1)  # IMAP SINCE is date-only

    def wanted(h: HeaderInfo) -> bool:
        if not h.message_id or h.message_id in known or h.message_id in by_id:
            return False
        refs = {h.in_reply_to, *h.references}
        return bool(refs & by_id.keys()) or h.from_addr in by_sender

    for incoming in mail.fetch_since(since, wanted):
        if incoming.message_id in known:
            continue
        refs = [r for r in [incoming.in_reply_to, *incoming.references] if r in by_id]
        vendor = by_id[refs[-1]].vendor if refs else by_sender.get(incoming.from_addr)
        if vendor is None:
            continue
        msg = Message(
            case_id=vendor.case_id,
            vendor_id=vendor.id,
            direction="in",
            kind="reply",
            status="received",
            subject=incoming.subject[:500],
            body=incoming.body,
            body_full=incoming.body_full,
            from_addr=incoming.from_addr,
            rfc_message_id=incoming.message_id,
            in_reply_to=incoming.in_reply_to,
            references=" ".join(incoming.references),
            received_at=_to_utc_naive(incoming.date) if incoming.date else utcnow(),
        )
        ctx.db.add(msg)
        ctx.db.flush()
        known.add(incoming.message_id)
        ctx.event(vendor.case_id, f"Reply received from {vendor.name}.", "success")
        ctx.enqueue("analyze_reply", case_id=vendor.case_id, payload={"message_id": msg.id})


def analyze_reply(ctx: StepContext, message_id: int) -> None:
    msg = ctx.db.get(Message, message_id)
    if msg is None or msg.vendor is None:
        return
    case, vendor = msg.case, msg.vendor
    data = case_dict(case)
    vendor_data = {"name": vendor.name, "website": vendor.website}
    email = {"from": msg.from_addr, "subject": msg.subject, "body": msg.body}
    existing = quote_dict(vendor.quote) if vendor.quote else None
    result = ctx.llm.structured(
        task="analyze_reply",
        prompt=prompts.analyze_prompt(data, vendor_data, email, existing),
        schema=ReplyAnalysis,
        effort="medium",
        context={"case": data, "vendor": vendor_data, "email": email, "existing_offer": existing},
    )
    msg.analysis = result.model_dump()

    if result.declined and not result.is_quote:
        vendor.declined = True
        ctx.event(case.id, f"{vendor.name} declined: {result.summary}", "warning")
        return

    quote = vendor.quote
    if not result.is_quote and quote is None:
        ctx.event(case.id, f"{vendor.name} replied: {result.summary}")
        return
    if quote is None:
        quote = Quote(case=case, vendor=vendor, revision=0)
        ctx.db.add(quote)
    vendor.declined = False
    quote.message_id = msg.id
    quote.source = "email"
    quote.revision = (quote.revision or 0) + 1
    if result.total_price is not None:
        quote.total_price = result.total_price
        quote.currency = result.currency.strip().upper()[:10]
        quote.price_basis = result.price_basis
    # keep earlier details when a follow-up email does not repeat them
    for field_name in ("price_text", "timeline", "valid_until", "conditions", "summary", "fit_notes"):
        value = getattr(result, field_name).strip()
        if value:
            setattr(quote, field_name, value)
    for field_name in ("includes", "excludes"):
        values = [v for v in getattr(result, field_name) if v.strip()]
        if values:
            setattr(quote, field_name, values)
    quote.missing_info = result.missing_info
    quote.vendor_questions = result.vendor_questions
    quote.fit_score = max(0, min(100, result.fit_score))
    price = f"{quote.total_price:,.0f} {quote.currency}".strip() if quote.total_price is not None else "no total yet"
    ctx.event(case.id, f"Offer from {vendor.name}: {price}. {result.summary}", "success")


def draft_reply(ctx: StepContext, vendor_id: int, intent: str = "clarify", instructions: str = "") -> None:
    vendor = ctx.db.get(Vendor, vendor_id)
    if vendor is None:
        return
    case = vendor.case
    data = case_dict(case)
    thread = [
        {
            "direction": "requester" if m.direction == "out" else "vendor",
            "date": m.timestamp.strftime("%Y-%m-%d %H:%M"),
            "subject": m.subject,
            "body": m.body,
        }
        for m in vendor.messages
        if m.status in ("sent", "received")
    ][-10:]
    offer = quote_dict(vendor.quote) if vendor.quote else None
    others = [quote_dict(q) for q in case.quotes if q.vendor_id != vendor.id and q.total_price is not None]
    result = ctx.llm.structured(
        task="draft_reply",
        prompt=prompts.reply_prompt(data, {"name": vendor.name}, thread, offer, others, intent, instructions),
        schema=EmailBody,
        effort="medium",
        context={"case": data, "vendor": {"name": vendor.name}, "thread": thread, "offer": offer,
                 "other_offers": others, "intent": intent, "instructions": instructions},
    )
    anchor = vendor.last_inbound or next(
        (m for m in reversed(vendor.messages) if m.direction == "out" and m.status == "sent"), None
    )
    references = []
    if anchor:
        references = [*anchor.references.split(), anchor.rfc_message_id]
    msg = Message(
        case=case,
        vendor=vendor,
        direction="out",
        kind="reply",
        status="draft",
        subject=reply_subject(anchor.subject if anchor else case.rfq_subject)[:500],
        body=result.body.strip(),
        to_addr=(vendor.last_inbound.from_addr if vendor.last_inbound else "") or vendor.email,
        in_reply_to=anchor.rfc_message_id if anchor else "",
        references=" ".join(r for r in references if r),
    )
    ctx.db.add(msg)
    ctx.event(case.id, f"Reply to {vendor.name} drafted ({intent}). Review it on the Outreach tab.", "success")


def compare_quotes(ctx: StepContext, case_id: int) -> None:
    case = _get_case(ctx, case_id)
    offers = [quote_dict(q) for q in case.quotes if not q.vendor.excluded]
    if not offers:
        raise StepError("There are no offers to compare yet.")
    data = case_dict(case)
    result = ctx.llm.structured(task="compare", prompt=prompts.compare_prompt(data, offers), schema=Comparison,
                                effort="high", context={"case": data, "offers": offers})
    valid_ids = {o["vendor_id"] for o in offers}
    recommendation = result.model_dump()
    recommendation["ranking"] = sorted(
        (r for r in recommendation["ranking"] if r["vendor_id"] in valid_ids), key=lambda r: r["rank"]
    )
    if recommendation["recommended_vendor_id"] not in valid_ids:
        recommendation["recommended_vendor_id"] = None
    recommendation["created_at"] = utcnow().isoformat()
    recommendation["offer_count"] = len(offers)
    case.recommendation = recommendation
    ctx.event(case.id, f"Offers compared: {result.headline}", "success")


HANDLERS = {
    "structure_brief": structure_brief,
    "find_vendors": find_vendors,
    "discover_contacts": discover_contacts,
    "draft_rfq": draft_rfq,
    "send_message": send_message,
    "sync_inbox": sync_inbox,
    "analyze_reply": analyze_reply,
    "draft_reply": draft_reply,
    "compare_quotes": compare_quotes,
}
