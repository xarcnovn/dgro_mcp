"""Presentation helpers: what the case page should highlight as the next step."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Case, Job


@dataclass
class NextAction:
    text: str
    tab: str
    button: str = ""  # label of the button on that tab to press, if any


def next_action(case: Case, busy: list[Job], can_receive: bool, poll_minutes: int) -> NextAction:
    if case.status == "closed":
        return NextAction("This case is closed. Reopen it to continue.", "quotes")
    if case.status == "decided":
        return NextAction("Offer chosen. Send the acceptance and polite declines, then close the case.", "outreach")
    if case.brief_status != "confirmed":
        if not case.summary:
            return NextAction("Claude is turning your request into a brief…", "brief")
        open_questions = [q for q in case.questions or [] if not q.get("answer")]
        if open_questions:
            return NextAction(f"Answer {len(open_questions)} open question(s) (optional), check the brief and "
                              "confirm it.", "brief", "Confirm brief")
        return NextAction("Check the brief and confirm it to start looking for vendors.", "brief", "Confirm brief")

    vendors = case.active_vendors
    with_email = [v for v in vendors if v.email]
    drafts = case.draft_messages
    replies_pending_analysis = any(j.kind == "analyze_reply" for j in busy)
    if not vendors:
        if any(j.kind == "find_vendors" for j in busy):
            return NextAction("Searching the web for vendors…", "vendors")
        return NextAction("No vendors yet. Search again or add vendors you know.", "vendors", "Find vendors")
    if drafts:
        return NextAction(f"Review and approve {len(drafts)} email draft(s). Nothing is sent without your "
                          "approval.", "outreach", "Approve & send")
    if not case.rfq_body:
        return NextAction("Write the quote request email (or let Claude draft it).", "outreach")
    uncontacted = [v for v in with_email if v.selected and not v.has_rfq]
    if uncontacted and not case.sent_messages:
        return NextAction(f"Create quote requests for {len(uncontacted)} vendor(s) with an email address.",
                          "outreach", "Create drafts")
    if not with_email:
        return NextAction("None of the vendors has an email address yet - add one on the Vendors tab.", "vendors")
    if case.sent_messages and not case.quotes:
        if replies_pending_analysis:
            return NextAction("Reading a vendor reply…", "outreach")
        if can_receive:
            return NextAction(f"Waiting for replies. The inbox is checked every {poll_minutes} min.", "outreach")
        return NextAction("Waiting for replies. Sandbox mode: paste a vendor's reply into their thread to "
                          "continue.", "outreach")
    if case.quotes:
        rec = case.recommendation or {}
        if rec.get("offer_count") != len(case.quotes):
            return NextAction(f"{len(case.quotes)} offer(s) in. Compare them with Claude or choose one.", "quotes",
                              "Compare offers")
        return NextAction("Recommendation ready. Choose an offer when you are happy with it.", "quotes")
    return NextAction("Keep going on the Outreach tab.", "outreach")
