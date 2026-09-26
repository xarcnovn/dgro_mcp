"""The case workflow end to end with the offline model, plus job-queue behaviour."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from dgro.db import utcnow
from dgro.llm.base import LLMError
from dgro.llm.fake_llm import FakeLLM
from dgro.models import Case, Event, Job, Message, Vendor
from dgro.runtime import build_runtime
from dgro.services.mail import IncomingEmail, SandboxMail
from dgro.workflow import actions
from dgro.workflow.actions import ActionError

from .conftest import make_settings

REQUEST = ("Remont łazienki 9 m2 w Krakowie. Nowe płytki ok. 30 m2, prysznic walk-in, montaż WC i umywalki. "
           "Płytki kupuję sam.")


def new_case(rt, **form) -> int:
    with rt.session() as db:
        case = actions.create_case(db, rt.queue, rt.settings, {"request_text": REQUEST, "budget": "20 000 zł", **form})
        db.commit()
        return case.id


def confirm(rt, case_id: int) -> None:
    with rt.session() as db:
        case = db.get(Case, case_id)
        form = {"title": case.title, "summary": case.summary, "requirements": "\n".join(case.requirements),
                "vendor_language": case.vendor_language, "country_code": case.country_code,
                "search_queries": "\n".join(case.search_queries), "answer_0": "w listopadzie"}
        actions.save_brief(db, rt.queue, case, form, "confirm")
        db.commit()


def test_full_case_flow(rt):
    case_id = new_case(rt)
    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        assert case.stage == "brief" and case.summary and case.city == "Krakow"
        assert case.vendor_language == "pl" and case.questions

    confirm(rt, case_id)
    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        assert case.brief_status == "confirmed"
        assert case.questions[0]["answer"] == "w listopadzie"
        assert len(case.vendors) == 4
        assert [v.contact_status for v in case.vendors].count("found") == 3
        assert case.rfq_body and "{vendor_name}" in case.rfq_body
        assert case.stage == "outreach"
        assert actions.create_rfq_drafts(db, case) == 3
        db.commit()
        drafts = case.draft_messages
        assert all("{vendor_name}" not in m.body for m in drafts)
        assert drafts[0].vendor.name in drafts[0].body
        sent, problems = actions.approve_all(db, rt.queue, case)
        db.commit()
        assert (sent, problems) == (3, [])

    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        assert len(case.sent_messages) == 3 and case.stage == "quotes"
        assert all(m.rfc_message_id.startswith("<") for m in case.sent_messages)
        v1, v2, v3 = case.vendors[:3]
        actions.simulate_reply(db, rt.queue, v1, "Dzień dobry, całość 23 500 zł, 3 tygodnie. Czy płytki są już kupione?")
        actions.simulate_reply(db, rt.queue, v2, "Wycena: 19 800 zł, termin 4 tygodnie.")
        actions.simulate_reply(db, rt.queue, v3, "Niestety nie jesteśmy w stanie podjąć się zlecenia.")
        db.commit()
    assert len(list((rt.settings.outbox_dir).glob("*.eml"))) == 3

    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        prices = sorted(q.total_price for q in case.quotes)
        assert prices == [19800.0, 23500.0]
        assert {v.name: v.pipeline_status for v in case.vendors}[case.vendors[2].name] == "declined"
        assert case.best_quote.total_price == 19800.0
        assert case.stage == "decision"
        replies = [m for m in case.inbound_messages]
        assert all(m.in_reply_to for m in replies)
        actions.request_reply_draft(db, rt.queue, case.vendors[0], "negotiate", "")
        actions.compare(db, rt.queue, case)
        db.commit()

    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        rec = case.recommendation
        cheapest = next(q.vendor_id for q in case.quotes if q.total_price == 19800.0)
        assert rec["recommended_vendor_id"] == cheapest and rec["offer_count"] == 2
        reply = case.vendors[0].messages[-1]
        assert reply.status == "draft" and reply.subject.startswith("Re: ")
        assert reply.in_reply_to == case.vendors[0].last_inbound.rfc_message_id
        actions.choose_vendor(db, case, db.get(Vendor, cheapest))
        assert actions.draft_decision_emails(db, rt.queue, case) == 2  # the vendor who declined is skipped
        db.commit()

    rt.worker.run_pending()
    with rt.session() as db:
        case = db.get(Case, case_id)
        assert case.status == "decided"
        statuses = {v.pipeline_status for v in case.vendors}
        assert {"chosen", "not chosen", "declined"} <= statuses
        failed = [j for j in case.jobs if j.status == "failed"]
        assert failed == []


def test_enqueue_deduplicates_waiting_jobs(rt):
    case_id = new_case(rt)
    with rt.session() as db:
        first = rt.queue.enqueue(db, "structure_brief", case_id=case_id)
        second = rt.queue.enqueue(db, "structure_brief", case_id=case_id)
        other = rt.queue.enqueue(db, "discover_contacts", case_id=case_id, payload={"vendor_id": 1})
        db.commit()
        assert first.id == second.id != other.id


class FlakyLLM(FakeLLM):
    def __init__(self, failures: int, retryable: bool = True):
        self.failures = failures
        self.retryable = retryable

    def structured(self, **kwargs):
        if self.failures:
            self.failures -= 1
            raise LLMError("temporary outage", retryable=self.retryable)
        return super().structured(**kwargs)


def test_transient_failures_are_retried_with_backoff(tmp_path):
    rt = build_runtime(make_settings(tmp_path), llm=FlakyLLM(failures=1))
    case_id = new_case(rt)
    rt.worker.run_pending()
    with rt.session() as db:
        job = db.scalars(select(Job).where(Job.case_id == case_id)).one()
        assert job.status == "queued" and job.attempts == 1 and job.run_after > utcnow()
        job.run_after = utcnow()  # skip the wait
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        job = db.scalars(select(Job).where(Job.case_id == case_id)).one()
        assert job.status == "succeeded" and job.attempts == 2
        levels = [e.level for e in db.scalars(select(Event).where(Event.case_id == case_id))]
        assert "warning" in levels


def test_permanent_failures_are_reported_and_retryable_by_user(tmp_path):
    rt = build_runtime(make_settings(tmp_path), llm=FlakyLLM(failures=1, retryable=False))
    case_id = new_case(rt)
    rt.worker.run_pending()
    with rt.session() as db:
        job = db.scalars(select(Job).where(Job.case_id == case_id)).one()
        assert job.status == "failed" and "temporary outage" in job.error
        assert db.scalars(select(Event).where(Event.level == "error")).first() is not None
        actions.retry_job(db, rt.queue, job)
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        assert db.get(Case, case_id).summary


def test_restart_never_resends_an_email_in_unknown_state(rt):
    case_id = new_case(rt)
    with rt.session() as db:
        vendor = Vendor(case_id=case_id, name="Firma", email="biuro@firma.pl")
        db.add(vendor)
        db.flush()
        msg = Message(case_id=case_id, vendor_id=vendor.id, direction="out", status="sending", subject="s", body="b")
        db.add(msg)
        db.commit()
        msg_id = msg.id
    rt.worker.recover()
    with rt.session() as db:
        msg = db.get(Message, msg_id)
        assert msg.status == "failed" and "Sent folder" in msg.error


def test_approval_guards(rt):
    case_id = new_case(rt)
    with rt.session() as db:
        vendor = Vendor(case_id=case_id, name="Firma", email="biuro@firma.pl")
        db.add(vendor)
        db.flush()
        msg = Message(case_id=case_id, vendor_id=vendor.id, direction="out", status="draft", subject="Re: x",
                      body="Termin: [TODO: preferred start date]")
        db.add(msg)
        db.flush()
        with pytest.raises(ActionError, match="TODO"):
            actions.approve_message(db, rt.queue, msg)
        with pytest.raises(ActionError, match="Confirm the brief"):
            actions.search_vendors(db, rt.queue, db.get(Case, case_id))


class RecordingMail(SandboxMail):
    """smtp-like backend that records sends and serves a canned inbox."""

    name = "smtp"
    can_receive = True

    def __init__(self, outbox_dir, inbox=None):
        super().__init__(outbox_dir)
        self.sent = []
        self.inbox = inbox or []

    def send(self, message):
        self.sent.append(message)
        return "sent"

    def fetch_since(self, since, wanted):
        from dgro.services.mail import HeaderInfo

        return [m for m in self.inbox
                if wanted(HeaderInfo(m.message_id, m.from_addr, m.in_reply_to, m.references))]


def test_reserved_demo_addresses_are_never_emailed_for_real(tmp_path):
    backend = RecordingMail(tmp_path / "outbox")
    rt = build_runtime(make_settings(tmp_path), mail=backend)
    case_id = new_case(rt)
    with rt.session() as db:
        vendor = Vendor(case_id=case_id, name="Demo", email="oferty@nova-demo.example")
        db.add(vendor)
        db.flush()
        msg = Message(case_id=case_id, vendor_id=vendor.id, direction="out", status="draft", subject="s", body="b")
        db.add(msg)
        db.flush()
        actions.approve_message(db, rt.queue, msg)
        db.commit()
        msg_id = msg.id
    rt.worker.run_pending()
    with rt.session() as db:
        assert db.get(Message, msg_id).status == "failed"
    assert backend.sent == []


def test_inbox_sync_matches_replies_by_headers_then_sender(tmp_path):
    backend = RecordingMail(tmp_path / "outbox")
    rt = build_runtime(make_settings(tmp_path), mail=backend)
    case_id = new_case(rt)
    with rt.session() as db:
        v1 = Vendor(case_id=case_id, name="Alfa", email="biuro@alfa.pl")
        v2 = Vendor(case_id=case_id, name="Beta", email="oferty@beta.pl")
        db.add_all([v1, v2])
        db.flush()
        for vendor in (v1, v2):
            msg = Message(case_id=case_id, vendor_id=vendor.id, direction="out", status="draft",
                          subject="Zapytanie", body="Prośba o wycenę")
            db.add(msg)
            db.flush()
            actions.approve_message(db, rt.queue, msg)
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        sent = {m.vendor.name: m.rfc_message_id for m in db.scalars(select(Message).where(Message.status == "sent"))}
    assert len(backend.sent) == 2 and backend.sent[0].message_id == sent["Alfa"]

    backend.inbox = [
        # answered from a personal address, matched through In-Reply-To
        IncomingEmail(message_id="<r1@alfa.pl>", from_addr="jan@alfa.pl", from_name="Jan", subject="Re: Zapytanie",
                      body="Cena 15 000 zł, 2 tygodnie.", body_full="", in_reply_to=sent["Alfa"],
                      references=[sent["Alfa"]], date=datetime(2026, 9, 20, 10, 0)),
        # no threading headers, matched by the vendor's address
        IncomingEmail(message_id="<r2@beta.pl>", from_addr="oferty@beta.pl", from_name="", subject="Oferta",
                      body="Koszt 17 000 zł.", body_full=""),
        # unrelated mail is ignored
        IncomingEmail(message_id="<spam@shop.com>", from_addr="news@shop.com", from_name="", subject="Promo",
                      body="Sale!", body_full=""),
    ]
    with rt.session() as db:
        actions.sync_inbox(db, rt.queue)
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        inbound = {m.vendor.name: m for m in db.scalars(select(Message).where(Message.direction == "in"))}
        assert set(inbound) == {"Alfa", "Beta"}
        quotes = {q.vendor.name: q.total_price for q in db.get(Case, case_id).quotes}
        assert quotes == {"Alfa": 15000.0, "Beta": 17000.0}
        # replies to a vendor go to the address they wrote from
        actions.request_reply_draft(db, rt.queue, inbound["Alfa"].vendor, "clarify", "")
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        draft = db.scalars(select(Message).where(Message.status == "draft")).one()
        assert draft.to_addr == "jan@alfa.pl" and draft.in_reply_to == "<r1@alfa.pl>"
        assert sent["Alfa"] in draft.references.split()
    # a second sync does not import the same replies twice
    with rt.session() as db:
        actions.sync_inbox(db, rt.queue)
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        assert len(list(db.scalars(select(Message).where(Message.direction == "in")))) == 2


def test_followup_reply_keeps_earlier_offer_details(rt):
    case_id = new_case(rt)
    with rt.session() as db:
        vendor = Vendor(case_id=case_id, name="Firma", email="biuro@firma.pl")
        db.add(vendor)
        db.flush()
        actions.simulate_reply(db, rt.queue, vendor, "Cena 12 000 zł, termin 3 tygodnie.")
        db.commit()
        vendor_id = vendor.id
    rt.worker.run_pending()
    with rt.session() as db:
        vendor = db.get(Vendor, vendor_id)
        actions.simulate_reply(db, rt.queue, vendor, "Tak, możemy zacząć od poniedziałku.")
        db.commit()
    rt.worker.run_pending()
    with rt.session() as db:
        quote = db.get(Vendor, vendor_id).quote
        assert quote.total_price == 12000.0 and quote.timeline == "3 tygodnie" and quote.revision == 2


def test_manual_vendor_and_quote(rt):
    case_id = new_case(rt)
    with rt.session() as db:
        case = db.get(Case, case_id)
        vendor = actions.add_vendor(db, rt.queue, case, {"name": "Znajomy Hydraulik", "email": "jan@gmail.com"})
        with pytest.raises(ActionError):
            actions.add_vendor(db, rt.queue, case, {"name": "X", "email": "not-an-email"})
        quote = actions.save_manual_quote(db, case, {"vendor_id": str(vendor.id), "total_price": "18 500,50",
                                                     "currency": "pln", "timeline": "od listopada"})
        db.commit()
        assert quote.total_price == 18500.5 and quote.currency == "PLN" and quote.source == "manual"
        assert vendor.contact_status == "manual"
