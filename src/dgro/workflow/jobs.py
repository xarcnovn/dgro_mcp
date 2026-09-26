"""Durable background jobs backed by SQLite.

Every slow step (Claude calls, scraping, sending, inbox sync) is a row in `jobs`, executed by a small pool of
worker threads in the server process. Jobs survive restarts, retry transient failures with backoff, and record
failures on the case timeline so the UI can show them and offer a retry.
"""

from __future__ import annotations

import inspect
import logging
import threading
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import utcnow
from ..llm.base import LLMError
from ..models import Event, Job, Message

if TYPE_CHECKING:
    from ..runtime import Runtime

log = logging.getLogger(__name__)

RETRY_DELAYS = [20, 90, 300]  # seconds, per attempt

LABELS = {
    "structure_brief": "Drafting the brief",
    "find_vendors": "Searching the web for vendors",
    "discover_contacts": "Looking up contact details",
    "draft_rfq": "Writing the quote request email",
    "send_message": "Sending email",
    "sync_inbox": "Checking the inbox for replies",
    "analyze_reply": "Reading a vendor reply",
    "draft_reply": "Drafting a reply",
    "compare_quotes": "Comparing offers",
}


class StepError(Exception):
    """Expected failure with a message meant for the user."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (LLMError, StepError)):
        return exc.retryable
    return isinstance(exc, (httpx.TransportError, TimeoutError, ConnectionError))


@dataclass
class StepContext:
    db: Session
    rt: Runtime
    job: Job | None = None

    @property
    def settings(self):
        return self.rt.settings

    @property
    def llm(self):
        return self.rt.llm

    @property
    def mail(self):
        return self.rt.mail

    def event(self, case_id: int | None, message: str, level: str = "info") -> None:
        if case_id is not None:
            self.db.add(Event(case_id=case_id, level=level, message=message))

    def enqueue(self, kind: str, *, case_id: int | None = None, payload: dict[str, Any] | None = None) -> Job:
        return self.rt.queue.enqueue(self.db, kind, case_id=case_id, payload=payload)


class JobQueue:
    def __init__(self) -> None:
        self.wakeup = threading.Event()

    def enqueue(
        self,
        db: Session,
        kind: str,
        *,
        case_id: int | None = None,
        payload: dict[str, Any] | None = None,
        max_attempts: int = 3,
    ) -> Job:
        """Add a job unless an identical one is already waiting or running (protects against double clicks)."""
        payload = payload or {}
        case_filter = Job.case_id.is_(None) if case_id is None else Job.case_id == case_id
        for job in db.scalars(select(Job).where(Job.kind == kind, case_filter,
                                                Job.status.in_(("queued", "running")))):
            if job.payload == payload:
                return job
        job = Job(kind=kind, case_id=case_id, payload=payload, label=LABELS.get(kind, kind),
                  max_attempts=max_attempts)
        db.add(job)
        db.flush()
        self.wakeup.set()
        return job


class Worker:
    def __init__(self, runtime: Runtime, threads: int = 2, poll_interval: float = 1.0):
        self.rt = runtime
        self.threads = max(1, threads)
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._claim_lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._last_inbox_sync = 0.0

    # --- lifecycle ---------------------------------------------------------------------------------
    def start(self) -> None:
        self.recover()
        self._stop.clear()
        for i in range(self.threads):
            thread = threading.Thread(target=self._loop, name=f"dgro-worker-{i}", daemon=True)
            thread.start()
            self._threads.append(thread)
        scheduler = threading.Thread(target=self._scheduler_loop, name="dgro-scheduler", daemon=True)
        scheduler.start()
        self._threads.append(scheduler)
        log.info("worker started with %d threads", self.threads)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop taking jobs. A step still waiting on the network is abandoned and requeued on next start."""
        self._stop.set()
        self.rt.queue.wakeup.set()
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            thread.join(max(0.0, deadline - time.monotonic()))
        self._threads.clear()

    def recover(self) -> None:
        """Requeue jobs interrupted by a restart; never re-send an email whose delivery state is unknown."""
        with self.rt.session() as db:
            db.execute(update(Job).where(Job.status == "running").values(status="queued"))
            for msg in db.scalars(select(Message).where(Message.status == "sending")):
                msg.status = "failed"
                msg.error = ("Interrupted while sending - it may or may not have been delivered. "
                             "Check your Sent folder before retrying.")
            db.commit()

    # --- execution ---------------------------------------------------------------------------------
    def _loop(self) -> None:
        while not self._stop.is_set():
            job_id = self._claim()
            if job_id is None:
                self.rt.queue.wakeup.wait(self.poll_interval)
                self.rt.queue.wakeup.clear()
                continue
            self.execute(job_id)

    def _scheduler_loop(self) -> None:
        while not self._stop.wait(5.0):
            try:
                self._maybe_schedule_inbox_sync()
            except Exception:  # noqa: BLE001 - keep the scheduler alive
                log.exception("scheduler error")

    def _maybe_schedule_inbox_sync(self) -> None:
        if not self.rt.mail.can_receive:
            return
        now = time.monotonic()
        if now - self._last_inbox_sync < self.rt.settings.inbox_poll_seconds:
            return
        self._last_inbox_sync = now
        with self.rt.session() as db:
            has_sent = db.scalar(select(Message.id).where(Message.direction == "out", Message.status == "sent")
                                 .limit(1))
            if has_sent:
                self.rt.queue.enqueue(db, "sync_inbox")
                db.commit()

    def run_pending(self, limit: int = 200) -> int:
        """Process queued jobs synchronously until none are left (tests and CLI)."""
        done = 0
        while done < limit:
            job_id = self._claim()
            if job_id is None:
                break
            self.execute(job_id)
            done += 1
        return done

    def _claim(self) -> int | None:
        with self._claim_lock, self.rt.session() as db:
            job_id = db.scalar(
                select(Job.id).where(Job.status == "queued", Job.run_after <= utcnow()).order_by(Job.id).limit(1)
            )
            if job_id is None:
                return None
            claimed = db.execute(
                update(Job).where(Job.id == job_id, Job.status == "queued")
                .values(status="running", started_at=utcnow(), attempts=Job.attempts + 1)
            ).rowcount
            db.commit()
            return job_id if claimed == 1 else None

    def execute(self, job_id: int) -> None:
        from .steps import HANDLERS

        with self.rt.session() as db:
            job = db.get(Job, job_id)
            if job is None:
                return
            handler = HANDLERS.get(job.kind)
            started = time.monotonic()
            log.info("job %s %s (case %s) started", job.id, job.kind, job.case_id)
            try:
                if handler is None:
                    raise StepError(f"unknown job kind {job.kind!r}")
                kwargs = dict(job.payload)
                if "case_id" in inspect.signature(handler).parameters:
                    kwargs.setdefault("case_id", job.case_id)
                handler(StepContext(db=db, rt=self.rt, job=job), **kwargs)
                job.status = "succeeded"
                job.error = ""
                job.finished_at = utcnow()
                db.commit()
                log.info("job %s %s finished in %.1fs", job_id, job.kind, time.monotonic() - started)
            except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
                db.rollback()
                log.warning("job %s failed after %.1fs: %s", job_id, time.monotonic() - started, exc)
                self._record_failure(db, job_id, exc)

    def _record_failure(self, db: Session, job_id: int, exc: BaseException) -> None:
        job = db.get(Job, job_id)
        if job is None:
            return
        message = str(exc) or exc.__class__.__name__
        if not isinstance(exc, (LLMError, StepError)):
            log.exception("job %s (%s) crashed", job.id, job.kind, exc_info=exc)
        if is_retryable(exc) and job.attempts < job.max_attempts:
            delay = RETRY_DELAYS[min(job.attempts - 1, len(RETRY_DELAYS) - 1)]
            job.status = "queued"
            job.run_after = utcnow() + timedelta(seconds=delay)
            job.error = message
            if job.case_id:
                db.add(Event(case_id=job.case_id, level="warning",
                             message=f"{job.label} hit a temporary problem, retrying in {delay}s: {message}"))
        else:
            job.status = "failed"
            job.finished_at = utcnow()
            job.error = message
            if job.case_id:
                db.add(Event(case_id=job.case_id, level="error", message=f"{job.label} failed: {message}"))
        db.commit()
