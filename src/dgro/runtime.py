"""Wires settings, database, model backend, email backend and the job worker together."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .db import init_db, make_engine, make_session_factory
from .llm import LLM, build_llm
from .services.mail import MailBackend, build_mail
from .workflow.jobs import JobQueue, Worker


@dataclass
class Runtime:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    llm: LLM
    mail: MailBackend
    queue: JobQueue
    worker: Worker

    def session(self) -> Session:
        return self.session_factory()


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpx2", "anthropic._base_client"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def build_runtime(
    settings: Settings | None = None, *, llm: LLM | None = None, mail: MailBackend | None = None
) -> Runtime:
    settings = settings or get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.db_path)
    init_db(engine)
    session_factory = make_session_factory(engine)
    queue = JobQueue()
    runtime = Runtime(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        llm=llm or build_llm(settings),
        mail=mail or build_mail(settings),
        queue=queue,
        worker=None,  # type: ignore[arg-type]  # set below
    )
    runtime.worker = Worker(runtime, threads=settings.workers)
    return runtime
