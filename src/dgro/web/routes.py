"""HTTP routes. Pages are GET; every change is a form POST that redirects back to the case (PRG pattern)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import FormData

from ..models import STAGES, Case, Event, Job, Message, Vendor
from ..runtime import Runtime
from ..workflow import actions
from ..workflow.actions import ActionError
from .app import templates
from .view import next_action

router = APIRouter()
TABS = ["brief", "vendors", "outreach", "quotes", "activity"]


def get_rt(request: Request) -> Runtime:
    return request.app.state.rt


def get_db(request: Request) -> Iterator[Session]:
    db = get_rt(request).session()
    try:
        yield db
    finally:
        db.close()


def case_url(case_id: int, tab: str = "", notice: str = "", error: str = "", anchor: str = "") -> str:
    params = {k: v for k, v in (("tab", tab), ("notice", notice), ("error", error)) if v}
    url = f"/cases/{case_id}" + (f"?{urlencode(params)}" if params else "")
    return url + (f"#{anchor}" if anchor else "")


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def load_case(db: Session, case_id: int) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise HTTPException(404)
    return case


def load_vendor(db: Session, case: Case, vendor_id: int) -> Vendor:
    vendor = db.get(Vendor, vendor_id)
    if vendor is None or vendor.case_id != case.id:
        raise HTTPException(404)
    return vendor


ActionFn = Callable[[Session, Runtime, Case, dict[str, str], FormData], "str | tuple[str, str] | None"]


async def run_action(request: Request, case_id: int, tab: str, fn: ActionFn) -> RedirectResponse:
    """Read the form, run `fn` in a worker thread inside one transaction, and redirect back to the case.

    `fn` returns a notice for the user, or a (notice, tab) pair to land on a different tab.
    """
    form = await request.form()
    data = actions.form_to_dict(form)
    rt = get_rt(request)

    def work() -> str:
        with rt.session() as db:
            case = load_case(db, case_id)
            try:
                result = fn(db, rt, case, data, form) or ""
                notice, target = result if isinstance(result, tuple) else (result, tab)
                db.commit()
                return case_url(case_id, target, notice=notice)
            except ActionError as exc:
                db.rollback()
                return case_url(case_id, tab, error=str(exc))

    return redirect(await run_in_threadpool(work))


# --- pages ---------------------------------------------------------------------------------------------
@router.get("/healthz")
def healthz(db: Session = Depends(get_db)) -> dict[str, Any]:
    db.execute(select(1))
    return {"ok": True}


@router.get("/", response_class=HTMLResponse)
def cases_index(request: Request, show: str = "open", db: Session = Depends(get_db)):
    query = select(Case).options(selectinload(Case.vendors).selectinload(Vendor.messages),
                                 selectinload(Case.quotes), selectinload(Case.messages))
    last_activity = dict(db.execute(select(Event.case_id, func.max(Event.created_at)).group_by(Event.case_id)).all())
    cases = sorted(db.scalars(query), key=lambda c: last_activity.get(c.id) or c.updated_at, reverse=True)
    for case in cases:
        case.last_activity = max(filter(None, [last_activity.get(case.id), case.updated_at]))
    open_cases = [c for c in cases if c.status != "closed"]
    closed_cases = [c for c in cases if c.status == "closed"]
    busy_ids = set(db.scalars(select(Job.case_id).where(Job.status.in_(("queued", "running")))))
    return templates.TemplateResponse(request, "cases.html", {
        "cases": closed_cases if show == "closed" else open_cases,
        "show": show,
        "open_count": len(open_cases),
        "closed_count": len(closed_cases),
        "busy_ids": busy_ids,
        "stages": STAGES,
    })


@router.get("/cases/new", response_class=HTMLResponse)
def new_case_form(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "case_new.html", {"error": error, "form": {}})


@router.post("/cases")
async def create_case(request: Request):
    form = actions.form_to_dict(await request.form())
    rt = get_rt(request)

    def work() -> tuple[int | None, str]:
        with rt.session() as db:
            try:
                case = actions.create_case(db, rt.queue, rt.settings, form)
                db.commit()
                return case.id, ""
            except ActionError as exc:
                return None, str(exc)

    case_id, error = await run_in_threadpool(work)
    if case_id is None:
        return templates.TemplateResponse(request, "case_new.html", {"error": error, "form": form}, status_code=400)
    return redirect(case_url(case_id, "brief"))


@router.get("/cases/{case_id}", response_class=HTMLResponse)
def case_page(request: Request, case_id: int, tab: str = "", notice: str = "", error: str = "",
              db: Session = Depends(get_db)):
    rt = get_rt(request)
    # Read the change marker and job state before the case data: if a job finishes while the page renders,
    # the browser sees a newer version on its next poll and refreshes instead of showing stale data.
    version = _version(db, case_id)
    busy = actions.case_busy(db, case_id)
    case = load_case(db, case_id)
    action = next_action(case, busy, rt.mail.can_receive, max(1, rt.settings.inbox_poll_seconds // 60))
    tab = tab if tab in TABS else action.tab
    # Show a failure only while it is the latest attempt of that step (a later success or retry clears it).
    latest: dict[str, Job] = {}
    for job in case.jobs:
        latest[f"{job.kind}:{sorted(job.payload.items())}"] = job
    failed_jobs = [j for j in latest.values() if j.status == "failed"][-5:]
    vendor_by_id = {v.id: v for v in case.vendors}
    return templates.TemplateResponse(request, "case.html", {
        "case": case,
        "tab": tab,
        "tabs": TABS,
        "stages": STAGES,
        "busy": busy,
        "action": action,
        "notice": notice,
        "error": error,
        "failed_jobs": failed_jobs,
        "vendor_by_id": vendor_by_id,
        "version": version,
        "can_receive": rt.mail.can_receive,
    })


def _version(db: Session, case_id: int) -> str:
    """Cheap change marker for a case; the browser reloads when it changes."""
    event_id = db.scalar(select(func.max(Event.id)).where(Event.case_id == case_id)) or 0
    job_id = db.scalar(select(func.max(Job.id)).where(Job.case_id == case_id)) or 0
    finished = db.scalar(select(func.count(Job.id)).where(Job.case_id == case_id,
                                                          Job.status.in_(("succeeded", "failed")))) or 0
    message_id = db.scalar(select(func.max(Message.id)).where(Message.case_id == case_id)) or 0
    return f"{event_id}.{job_id}.{finished}.{message_id}"


@router.get("/cases/{case_id}/status")
def case_status(case_id: int, db: Session = Depends(get_db)) -> JSONResponse:
    busy = actions.case_busy(db, case_id)
    return JSONResponse({
        "busy": bool(busy),
        "jobs": [j.label for j in busy],
        "version": _version(db, case_id),
    })


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {"checks": None})


@router.post("/settings/test-email", response_class=HTMLResponse)
async def test_email(request: Request):
    rt = get_rt(request)
    checks = await run_in_threadpool(rt.mail.check)
    return templates.TemplateResponse(request, "settings.html", {"checks": checks})


# --- case actions --------------------------------------------------------------------------------------
@router.post("/cases/{case_id}/brief")
async def brief_save(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        action = data.get("action", "save")
        notice = actions.save_brief(db, rt.queue, case, data, action)
        return (notice, "vendors") if action == "confirm" else notice

    return await run_action(request, case_id, "brief", fn)


@router.post("/cases/{case_id}/brief/reopen")
async def brief_reopen(request: Request, case_id: int):
    return await run_action(request, case_id, "brief", lambda db, rt, case, d, f: actions.reopen_brief(db, case))


@router.post("/cases/{case_id}/state")
async def case_state(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        actions.set_case_status(db, case, data.get("status", ""))
        return "Case closed." if case.status == "closed" else "Case reopened."

    return await run_action(request, case_id, "quotes", fn)


@router.post("/cases/{case_id}/delete")
async def case_delete(request: Request, case_id: int):
    rt = get_rt(request)

    def work() -> None:
        with rt.session() as db:
            actions.delete_case(db, load_case(db, case_id))
            db.commit()

    await run_in_threadpool(work)
    return redirect("/")


@router.post("/cases/{case_id}/vendors/search")
async def vendors_search(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        actions.search_vendors(db, rt.queue, case)
        return "Searching the web for more vendors…"

    return await run_action(request, case_id, "vendors", fn)


@router.post("/cases/{case_id}/vendors")
async def vendor_add(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        vendor = actions.add_vendor(db, rt.queue, case, data)
        return f"Added {vendor.name}."

    return await run_action(request, case_id, "vendors", fn)


@router.post("/cases/{case_id}/vendors/{vendor_id}")
async def vendor_update(request: Request, case_id: int, vendor_id: int):
    def fn(db, rt, case, data, form):
        vendor = load_vendor(db, case, vendor_id)
        op = data.get("op", "save")
        if op == "save":
            actions.update_vendor(db, vendor, data)
            return f"Saved {vendor.name}."
        if op == "rescan":
            actions.rescan_vendor(db, rt.queue, vendor)
            return f"Scanning {vendor.website} for contact details…"
        if op in ("exclude", "include"):
            actions.set_vendor_flags(db, vendor, excluded=op == "exclude")
            return f"{vendor.name} {'excluded' if op == 'exclude' else 'restored'}."
        if op in ("select", "unselect"):
            actions.set_vendor_flags(db, vendor, selected=op == "select")
            return ""
        raise ActionError("Unknown operation.")

    return await run_action(request, case_id, "vendors", fn)


@router.post("/cases/{case_id}/rfq")
async def rfq_save(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        return actions.save_rfq(db, rt.queue, case, data, data.get("action", "save"))

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/drafts")
async def drafts_create(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        ids = [int(x) for x in form.getlist("vendor_ids") if str(x).isdigit()]
        if not ids:
            raise ActionError("Select at least one vendor.")
        if data.get("rfq_subject") is not None and data.get("rfq_body"):
            actions.save_rfq(db, rt.queue, case, data, "save")
        count = actions.create_rfq_drafts(db, case, ids)
        if not count:
            raise ActionError("No new drafts: the selected vendors already have one or lack an email address.")
        return f"{count} draft(s) created. Review them below, then approve."

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/messages/send-all")
async def messages_send_all(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        sent, problems = actions.approve_all(db, rt.queue, case)
        if problems and not sent:
            raise ActionError(" ".join(problems))
        note = f"{sent} email(s) queued for sending."
        return note + (f" Skipped: {' '.join(problems)}" if problems else "")

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/messages/{message_id}")
async def message_update(request: Request, case_id: int, message_id: int):
    def fn(db, rt, case, data, form):
        msg = db.get(Message, message_id)
        if msg is None or msg.case_id != case.id:
            raise HTTPException(404)
        op = data.get("op", "save")
        if op in ("save", "send"):
            actions.update_draft(db, msg, data)
        if op == "send":
            actions.approve_message(db, rt.queue, msg)
            return f"Sending to {msg.to_addr or msg.vendor.email}…"
        if op == "discard":
            actions.discard_message(db, msg)
            return "Draft discarded."
        return "Draft saved."

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/vendors/{vendor_id}/reply")
async def vendor_reply(request: Request, case_id: int, vendor_id: int):
    def fn(db, rt, case, data, form):
        vendor = load_vendor(db, case, vendor_id)
        actions.simulate_reply(db, rt.queue, vendor, data.get("body", ""))
        return f"Reply from {vendor.name} recorded - Claude is reading it…"

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/vendors/{vendor_id}/draft-reply")
async def vendor_draft_reply(request: Request, case_id: int, vendor_id: int):
    def fn(db, rt, case, data, form):
        vendor = load_vendor(db, case, vendor_id)
        actions.request_reply_draft(db, rt.queue, vendor, data.get("intent", "clarify"), data.get("instructions", ""))
        return f"Drafting a reply to {vendor.name}…"

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/inbox")
async def inbox_sync(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        if not rt.mail.can_receive:
            raise ActionError("Inbox checking needs DGRO_EMAIL_MODE=smtp with IMAP settings.")
        actions.sync_inbox(db, rt.queue, case.id)
        return "Checking the inbox…"

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/compare")
async def quotes_compare(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        actions.compare(db, rt.queue, case)
        return "Comparing offers…"

    return await run_action(request, case_id, "quotes", fn)


@router.post("/cases/{case_id}/quotes")
async def quote_manual(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        quote = actions.save_manual_quote(db, case, data)
        return f"Offer from {quote.vendor.name} saved."

    return await run_action(request, case_id, "quotes", fn)


@router.post("/cases/{case_id}/choose/{vendor_id}")
async def quote_choose(request: Request, case_id: int, vendor_id: int):
    def fn(db, rt, case, data, form):
        vendor = load_vendor(db, case, vendor_id)
        actions.choose_vendor(db, case, vendor)
        return f"{vendor.name} chosen."

    return await run_action(request, case_id, "quotes", fn)


@router.post("/cases/{case_id}/decision-emails")
async def decision_emails(request: Request, case_id: int):
    def fn(db, rt, case, data, form):
        count = actions.draft_decision_emails(db, rt.queue, case)
        return f"Drafting {count} email(s): acceptance for the chosen vendor, polite declines for the others…"

    return await run_action(request, case_id, "outreach", fn)


@router.post("/cases/{case_id}/jobs/{job_id}/retry")
async def job_retry(request: Request, case_id: int, job_id: int):
    def fn(db, rt, case, data, form):
        job = db.get(Job, job_id)
        if job is None or job.case_id != case.id:
            raise HTTPException(404)
        actions.retry_job(db, rt.queue, job)
        return f"Retrying: {job.label}."

    return await run_action(request, case_id, data_tab(request), fn)


def data_tab(request: Request) -> str:
    tab = request.query_params.get("tab", "activity")
    return tab if tab in TABS else "activity"
